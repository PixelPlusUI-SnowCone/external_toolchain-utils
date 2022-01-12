use anyhow::{anyhow, bail, ensure, Context, Result};
use regex::Regex;
use std::ffi::OsStr;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

const CHROMIUMOS_OVERLAY_REL_PATH: &str = "src/third_party/chromiumos-overlay";
const ANDROID_LLVM_REL_PATH: &str = "toolchain/llvm_android";

const CROS_MAIN_BRANCH: &str = "main";
const ANDROID_MAIN_BRANCH: &str = "master"; // nocheck

/// Context struct to keep track of both Chromium OS and Android checkouts.
#[derive(Debug)]
pub struct RepoSetupContext {
    pub cros_checkout: PathBuf,
    pub android_checkout: PathBuf,
    /// Run `repo sync` before doing any comparisons.
    pub sync_before: bool,
}

impl RepoSetupContext {
    pub fn setup(&self) -> Result<()> {
        if self.sync_before {
            {
                let crpp = self.cros_patches_path();
                let cros_git = crpp.parent().unwrap();
                git_cd_cmd(cros_git, ["checkout", CROS_MAIN_BRANCH])?;
            }
            {
                let anpp = self.android_patches_path();
                let android_git = anpp.parent().unwrap();
                git_cd_cmd(android_git, ["checkout", ANDROID_MAIN_BRANCH])?;
            }
            repo_cd_cmd(&self.cros_checkout, &["sync", CHROMIUMOS_OVERLAY_REL_PATH])?;
            repo_cd_cmd(&self.android_checkout, &["sync", ANDROID_LLVM_REL_PATH])?;
        }
        Ok(())
    }

    pub fn cros_repo_upload<S: AsRef<str>>(&self, reviewers: &[S]) -> Result<()> {
        let llvm_dir = self
            .cros_checkout
            .join(&CHROMIUMOS_OVERLAY_REL_PATH)
            .join("sys-devel/llvm");
        ensure!(
            llvm_dir.is_dir(),
            "CrOS LLVM dir {} is not a directory",
            llvm_dir.display()
        );
        Self::rev_bump_llvm(&llvm_dir)?;
        let mut extra_args = vec!["--label=Commit-Queue+1"];
        for reviewer in reviewers {
            extra_args.push("--re");
            extra_args.push(reviewer.as_ref());
        }
        Self::repo_upload(
            &self.cros_checkout,
            CROS_MAIN_BRANCH,
            CHROMIUMOS_OVERLAY_REL_PATH,
            &Self::build_commit_msg(
                "llvm: Synchronize patches from android",
                "android",
                "chromiumos",
                "BUG=None\nTEST=CQ",
            ),
            extra_args,
        )
    }

    pub fn android_repo_upload<S: AsRef<str>>(&self, reviewers: &[S]) -> Result<()> {
        let mut extra_args = Vec::new();
        // TODO(ajordanr): Presubmit ready can only be enabled if we
        // have the permissions.
        // extra_args.push("--label=Presubmit-Ready+1");
        for reviewer in reviewers {
            extra_args.push("--re");
            extra_args.push(reviewer.as_ref());
        }
        Self::repo_upload(
            &self.android_checkout,
            ANDROID_MAIN_BRANCH,
            ANDROID_LLVM_REL_PATH,
            &Self::build_commit_msg(
                "Synchronize patches from chromiumos",
                "chromiumos",
                "android",
                "Test: N/A",
            ),
            extra_args,
        )
    }

    /// Get the Android path to the PATCHES.json file
    pub fn android_patches_path(&self) -> PathBuf {
        self.android_checkout
            .join(&ANDROID_LLVM_REL_PATH)
            .join("patches/PATCHES.json")
    }

    /// Get the Chromium OS path to the PATCHES.json file
    pub fn cros_patches_path(&self) -> PathBuf {
        self.cros_checkout
            .join(&CHROMIUMOS_OVERLAY_REL_PATH)
            .join("sys-devel/llvm/files/PATCHES.json")
    }

    /// Return the contents of the old PATCHES.json from Chromium OS
    pub fn old_cros_patch_contents(&self, hash: &str) -> Result<String> {
        Self::old_file_contents(
            hash,
            &self.cros_checkout.join(CHROMIUMOS_OVERLAY_REL_PATH),
            Path::new("sys-devel/llvm/files/PATCHES.json"),
        )
    }

    /// Return the contents of the old PATCHES.json from android
    pub fn old_android_patch_contents(&self, hash: &str) -> Result<String> {
        Self::old_file_contents(
            hash,
            &self.android_checkout.join(ANDROID_LLVM_REL_PATH),
            Path::new("patches/PATCHES.json"),
        )
    }

    fn repo_upload<'a, I: IntoIterator<Item = &'a str>>(
        path: &Path,
        base_branch: &str,
        git_wd: &'a str,
        commit_msg: &str,
        extra_flags: I,
    ) -> Result<()> {
        let git_path = &path.join(&git_wd);
        ensure!(
            git_path.is_dir(),
            "git_path {} is not a directory",
            git_path.display()
        );
        let branch_name = "__patch_sync_tmp_branch";
        repo_cd_cmd(path, &["start", branch_name, git_wd])?;
        let res: Result<()> = {
            let base_args = ["upload", "--br", branch_name, "-y", "--verify"];
            let new_args = base_args
                .iter()
                .copied()
                .chain(extra_flags)
                .chain(["--", git_wd]);
            git_cd_cmd(git_path, &["add", "."])
                .and_then(|_| git_cd_cmd(git_path, &["commit", "-m", commit_msg]))
                .and_then(|_| repo_cd_cmd(path, new_args))
        };
        Self::cleanup_branch(git_path, base_branch, branch_name)
            .with_context(|| format!("cleaning up branch {}", branch_name))?;
        res
    }

    /// Clean up the git repo after we're done with it.
    fn cleanup_branch(git_path: &Path, base_branch: &str, rm_branch: &str) -> Result<()> {
        git_cd_cmd(git_path, ["restore", "."])?;
        git_cd_cmd(git_path, ["clean", "-fd"])?;
        git_cd_cmd(git_path, ["checkout", base_branch])?;
        git_cd_cmd(git_path, ["branch", "-D", rm_branch])?;
        Ok(())
    }

    /// Increment LLVM's revision number
    fn rev_bump_llvm(llvm_dir: &Path) -> Result<PathBuf> {
        let ebuild = find_ebuild(llvm_dir)
            .with_context(|| format!("finding ebuild in {} to rev bump", llvm_dir.display()))?;
        let ebuild_dir = ebuild.parent().unwrap();
        let suffix_matcher = Regex::new(r"-r([0-9]+)\.ebuild").unwrap();
        let ebuild_name = ebuild
            .file_name()
            .unwrap()
            .to_str()
            .ok_or_else(|| anyhow!("converting ebuild filename to utf-8"))?;
        let new_path = if let Some(captures) = suffix_matcher.captures(ebuild_name) {
            let full_suffix = captures.get(0).unwrap().as_str();
            let cur_version = captures.get(1).unwrap().as_str().parse::<u32>().unwrap();
            let new_filename =
                ebuild_name.replace(full_suffix, &format!("-r{}.ebuild", cur_version + 1_u32));
            let new_path = ebuild_dir.join(new_filename);
            fs::rename(&ebuild, &new_path)?;
            new_path
        } else {
            // File did not end in a revision. We should append -r1 to the end.
            let new_filename = ebuild.file_stem().unwrap().to_string_lossy() + "-r1.ebuild";
            let new_path = ebuild_dir.join(new_filename.as_ref());
            fs::rename(&ebuild, &new_path)?;
            new_path
        };
        Ok(new_path)
    }

    /// Return the contents of an old file in git
    fn old_file_contents(hash: &str, pwd: &Path, file: &Path) -> Result<String> {
        let git_ref = format!(
            "{}:{}",
            hash,
            file.to_str()
                .ok_or_else(|| anyhow!("failed to convert filepath to str"))?
        );
        let output = git_cd_cmd(pwd, &["show", &git_ref])?;
        if !output.status.success() {
            bail!("could not get old file contents for {}", &git_ref)
        }
        String::from_utf8(output.stdout)
            .with_context(|| format!("converting {} file contents to UTF-8", &git_ref))
    }

    /// Create the commit message
    fn build_commit_msg(subj: &str, from: &str, to: &str, footer: &str) -> String {
        format!(
            "[patch_sync] {}\n\n\
Copies new PATCHES.json changes from {} to {}.\n
For questions about this job, contact chromeos-toolchain@google.com\n\n
{}",
            subj, from, to, footer
        )
    }
}

/// Return the path of an ebuild located within the given directory.
fn find_ebuild(dir: &Path) -> Result<PathBuf> {
    // TODO(ajordanr): Maybe use OnceCell for this regex?
    let ebuild_matcher = Regex::new(r"(-r[0-9]+)?\.ebuild").unwrap();
    for entry in fs::read_dir(dir)? {
        let path = entry?.path();
        if let Some(name) = path.file_name() {
            if ebuild_matcher.is_match(
                name.to_str()
                    .ok_or_else(|| anyhow!("converting filepath to UTF-8"))?,
            ) {
                return Ok(path);
            }
        }
    }
    bail!("could not find ebuild")
}

/// Run a given git command from inside a specified git dir.
pub fn git_cd_cmd<I, S>(pwd: &Path, args: I) -> Result<Output>
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    let mut command = Command::new("git");
    command.current_dir(&pwd).args(args);
    let output = command.output()?;
    if !output.status.success() {
        bail!(
            "git command failed:\n  {:?}\nstdout --\n{}\nstderr --\n{}",
            command,
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr),
        );
    }
    Ok(output)
}

pub fn repo_cd_cmd<I, S>(pwd: &Path, args: I) -> Result<()>
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    let mut command = Command::new("repo");
    command.current_dir(&pwd).args(args);
    let status = command.status()?;
    if !status.success() {
        bail!("repo command failed:\n  {:?}  \n", command)
    }
    Ok(())
}

#[cfg(test)]
mod test {
    use super::*;
    use rand::prelude::Rng;
    use std::env;
    use std::fs::File;

    #[test]
    fn test_revbump_ebuild() {
        // Random number to append at the end of the test folder to prevent conflicts.
        let rng: u32 = rand::thread_rng().gen();
        let llvm_dir = env::temp_dir().join(format!("patch_sync_test_{}", rng));
        fs::create_dir(&llvm_dir).expect("creating llvm dir in temp directory");

        {
            // With revision
            let ebuild_name = "llvm-13.0_pre433403_p20211019-r10.ebuild";
            let ebuild_path = llvm_dir.join(ebuild_name);
            File::create(&ebuild_path).expect("creating test ebuild file");
            let new_ebuild_path =
                RepoSetupContext::rev_bump_llvm(&llvm_dir).expect("rev bumping the ebuild");
            assert!(new_ebuild_path.ends_with("llvm-13.0_pre433403_p20211019-r11.ebuild"));
            fs::remove_file(new_ebuild_path).expect("removing renamed ebuild file");
        }
        {
            // Without revision
            let ebuild_name = "llvm-13.0_pre433403_p20211019.ebuild";
            let ebuild_path = llvm_dir.join(ebuild_name);
            File::create(&ebuild_path).expect("creating test ebuild file");
            let new_ebuild_path =
                RepoSetupContext::rev_bump_llvm(&llvm_dir).expect("rev bumping the ebuild");
            assert!(new_ebuild_path.ends_with("llvm-13.0_pre433403_p20211019-r1.ebuild"));
            fs::remove_file(new_ebuild_path).expect("removing renamed ebuild file");
        }

        fs::remove_dir(&llvm_dir).expect("removing temp test dir");
    }
}

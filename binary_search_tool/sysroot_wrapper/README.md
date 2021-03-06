# Sysroot wrapper

This is a set of scripts to use when triaging compiler problem by using
the bisecting functionality included in the `sysroot_wrapper.hardened`.
The only script that you need to create for your triaging problem is the
`test_script.sh` (The ones in this directory are here only as an example).

Before running the binary searcher tool you will need to run the setup script:

```
./sysroot_wrapper/setup.sh ${board} ${remote_ip} ${package} ${reboot_option} ${use_flags}
```

This setup script will ensure your `$BISECT_DIR` is properly populated and
generate a common variable script for the convenience of the scripts in
`./sysroot_wrapper`

To run the binary searcher tool with these scripts, execute it like this:

```
./binary_search_state.py \
  --get_initial_items=./sysroot_wrapper/get_initial_items.sh \
  --switch_to_good=./sysroot_wrapper/switch_to_good.sh \
  --switch_to_bad=./sysroot_wrapper/switch_to_bad.sh \
  --test_script=./sysroot_wrapper/test_script.sh \
  --noincremental \
  --file_args \
  2>&1 | tee /tmp/binary_search.log
```

Finally once done you will want to run the cleanup script:
`./sysroot_wrapper/cleanup.sh`

For more information on how to use the `sysroot_wrapper` to do object file
triaging see: https://sites.google.com/a/google.com/chromeos-toolchain-team-home2/home/team-tools-and-scripts/bisecting-compiler-problems

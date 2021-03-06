# `run_bisect.py`

`run_bisect.py` is a wrapper around the general purpose
`binary_search_state.py`. It provides a user friendly interface for
bisecting various compilation errors.  The 2 currently provided
methods of bisecting are ChromeOS package and object bisection. Each
method defines a default set of options to pass to
`binary_search_state.py` and allow the user to override these defaults
(see the "Overriding" section).

Please note that all commands, examples, scripts, etc. are to be run from your
chroot unless stated otherwise.

## Bisection Methods

### ChromeOS Package

This method will bisect across all packages in a ChromeOS repository and find
the offending packages (according to your test script). This method takes the
following arguments:

* board: The board to bisect on. For example: daisy, falco, etc.
* remote: The IP address of the physical machine you're using to test with.

By default the ChromeOS package method will do a simple interactive test that
pings the machine and prompts the user if the machine is good.

1.  Setup: The ChromeOS package method requires that you have three build trees:

    ```
    /build/${board}.bad  - The build tree for your "bad" build
    /build/${board}.good - The build tree for your "good" build
    /build/${board}.work - A full copy of /build/${board}.bad
    ```

1.  Cleanup: run_bisect.py does most cleanup for you, the only thing required by
    the user is to cleanup all built images and the three build trees made in
    `/build/`

1.  Default Arguments:

    ```
    --get_initial_items='cros_pkg/get_initial_items.sh'
    --switch_to_good='cros_pkg/switch_to_good.sh'
    --switch_to_bad='cros_pkg/switch_to_bad.sh'
    --test_setup_script='cros_pkg/test_setup.sh'
    --test_script='cros_pkg/interactive_test.sh'
    --incremental
    --prune
    --file_args
    ```

1.  Additional Documentation: See `./cros_pkg/README.cros_pkg_triage` for full
    documentation of ChromeOS package bisection.

1.  Examples:

    1.  Basic interactive test package bisection, on daisy board:

        ```
        ./run_bisect.py package daisy 172.17.211.184
        ```

    2.  Basic boot test package bisection, on daisy board:

        ```
        ./run_bisect.py package daisy 172.17.211.184 -t cros_pkg/boot_test.sh
        ```

### ChromeOS Object

This method will bisect across all objects in a ChromeOS package and find
the offending objects (according to your test script). This method takes the
following arguments:

* board: The board to bisect on. For example: daisy, falco, etc.
* remote: The IP address of the physical machine you're using to test with.
* package: The package to bisect with. For example: chromeos-chrome.
* use_flags: (Optional) Use flags for emerge. For example: "-thinlto -cfi".
* noreboot: (Optional) Do not reboot after updating the package.
* dir: (Optional) the directory for your good/bad build trees. Defaults to
       $BISECT_DIR or /tmp/sysroot_bisect. This value will set $BISECT_DIR
       for all bisecting scripts.

By default the ChromeOS object method will do a simple interactive test that
pings the machine and prompts the user if the machine is good.

1.  Setup: The ChromeOS package method requires that you populate your good and
    bad set of objects. `sysroot_wrapper` will automatically detect the
    `BISECT_STAGE` variable and use this to populate emerged objects. Here is an
    example:

    ```
    # Defaults to /tmp/sysroot_bisect
    export BISECT_DIR="/path/to/where/you/want/to/store/builds/"

    export BISECT_STAGE="POPULATE_GOOD"
    ./switch_to_good_compiler.sh
    emerge-${board} -C ${package_to_bisect}
    emerge-${board} ${package_to_bisect}

    export BISECT_STAGE="POPULATE_BAD"
    ./switch_to_bad_compiler.sh
    emerge-${board} -C {package_to_bisect}
    emerge-${board} ${package_to_bisect}
    ```

1.  Cleanup: The user must clean up all built images and the populated object
    files.

1.  Default Arguments:

    ```
    --get_initial_items='sysroot_wrapper/get_initial_items.sh'
    --switch_to_good='sysroot_wrapper/switch_to_good.sh'
    --switch_to_bad='sysroot_wrapper/switch_to_bad.sh'
    --test_setup_script='sysroot_wrapper/test_setup.sh'
    --test_script='sysroot_wrapper/interactive_test.sh'
    --noincremental
    --prune
    --file_args
    ```

1.  Additional Documentation: See `./sysroot_wrapper/README` for full
    documentation of ChromeOS object file bisecting.

1.  Examples:

    1.  Basic interactive test object bisection, on daisy board for cryptohome
        package: `./run_bisect.py object daisy 172.17.211.184 cryptohome`

    2.  Basic boot test package bisection, on daisy board for cryptohome
        package: `./run_bisect.py object daisy 172.17.211.184 cryptohome
        --test_script=sysroot_wrapper/boot_test.sh`

### Android object

NOTE: Because this isn't a ChromeOS bisection tool, the concept of a
      chroot doesn't exist. Just run this tool from a normal shell.

This method will bisect across all objects in the Android source tree and
find the offending objects (according to your test script). This method takes
the following arguments:

*   `android_src`: The location of your android source tree

*   `num_jobs`: (Optional) The number of jobs to pass to make. This is dependent
    on how many cores your machine has. A good number is probably somewhere
    around 5 to 10.

*   `device_id`: (Optional) The serial code for the device you are testing on.
    This is used to determine which device should be used in case multiple
    devices are plugged into your computer. You can get serial code for your
    device by running "adb devices".

*   `dir`: (Optional) the directory for your good/bad build trees. Defaults to
    `$BISECT_DIR` or `~/ANDROID_BISECT/`. This value will set `$BISECT_DIR` for
    all bisecting scripts.

  By default the Android object method will do a simple interactive test that
  pings the machine and prompts the user if the machine is good.

1.  Setup: The Android object method requires that you populate your good and
    bad set of objects. The Android compiler wrapper will automatically detect
    the `BISECT_STAGE` variable and use this to populate emerged objects. Here
    is an example:

    ```
    # Defaults to ~/ANDROID_BISECT/
    export BISECT_DIR="/path/to/where/you/want/to/store/builds/"

    export BISECT_STAGE="POPULATE_GOOD"
    # Install the "good" compiler
    ./switch_to_good_compiler.sh
    make clean
    make -j <your_preferred_number_of_jobs>

    export BISECT_STAGE="POPULATE_BAD"
    # Install the "bad" compiler
    ./switch_to_bad_compiler.sh
    make clean
    make -j <your_preferred_number_of_jobs>
    ```

1.  Cleanup: The user must clean up all built images and the populated object
    files.

1.  Default Arguments:

    ```
    --get_initial_items='android/get_initial_items.sh'
    --switch_to_good='android/switch_to_good.sh'
    --switch_to_bad='android/switch_to_bad.sh'
    --test_setup_script='android/test_setup.sh'
    --test_script='android/interactive_test.sh'
    --incremental
    --prune
    --file_args
    ```

1.  Additional Documentation: See `./android/README.android` for full
    documentation of Android object file bisecting.

1.  Examples:

    1.  Basic interactive test android bisection, where the android source is at
        ~/android_src: `./run_bisect.py android ~/android_src`

    2. Basic boot test android bisection, where the android source is at
       `~/android_src`, and 10 jobs will be used to build android:
       `./run_bisect.py
       android ~/android_src --num_jobs=10
       --test_script=sysroot_wrapper/boot_test.sh`

### Resuming

`run_bisect.py` and `binary_search_state.py` offer the
ability to resume a bisection in case it was interrupted by a
SIGINT, power failure, etc. Every time the tool completes a
bisection iteration its state is saved to disk (usually to the file
`./bisect_driver.py.state`). If passed the --resume option, the tool
it will automatically detect the state file and resume from the last
completed iteration.

### Overriding

You can run `./run_bisect.py --help` or `./binary_search_state.py
--help` for a full list of arguments that can be overriden. Here are
a couple of examples:

Example 1 (do boot test instead of interactive test):

```
./run_bisect.py package daisy 172.17.211.182 --test_script=cros_pkg/boot_test.sh
```

Example 2 (do package bisector system test instead of interactive test, this
           is used to test the bisecting tool itself -- see comments in
           hash_test.sh for more details):

```
./run_bisect.py package daisy 172.17.211.182 \
    --test_script=common/hash_test.sh --test_setup_script=""
```

Example 3 (enable verbose mode, disable pruning, and disable verification):

```
./run_bisect.py package daisy 172.17.211.182
      --verbose --prune=False --verify=False
```

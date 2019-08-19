//  Copyright 2019 The Chromium OS Authors. All rights reserved.
//  Use of this source code is governed by a BSD-style license that can be
//  found in the LICENSE file.

package main

import (
	"path"
	"testing"
)

const oldClangHostWrapperPathForTest = "$CHROOT/usr/bin/clang_host_wrapper"
const oldGccHostWrapperPathForTest = "$CHROOT/../src/third_party/chromiumos-overlay/sys-devel/gcc/files/host_wrapper"
const crosClangHostGoldenDir = "testdata/cros_clang_host_golden"
const crosGccHostGoldenDir = "testdata/cros_gcc_host_golden"

func TestCrosClangHostConfig(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		useCCache := false
		cfg, err := getConfig("cros.host", useCCache, oldClangHostWrapperPathForTest, "123")
		if err != nil {
			t.Fatal(err)
		}
		ctx.updateConfig(cfg)

		gomaPath := path.Join(ctx.tempDir, "gomacc")
		ctx.writeFile(gomaPath, "")
		gomaEnv := "GOMACC_PATH=" + gomaPath

		goldenFiles := []goldenFile{
			createClangPathGoldenInputs(ctx, gomaEnv),
			createGoldenInputsForAllTargets("clang", mainCc),
			createGoldenInputsForAllTargets("clang", "-ftrapv", mainCc),
			createSanitizerGoldenInputs("clang"),
			createClangArgsGoldenInputs(),
			createBisectGoldenInputs(),
			createForceDisableWErrorGoldenInputs(),
			createClangTidyGoldenInputs(gomaEnv),
		}

		runGoldenRecords(ctx, crosClangHostGoldenDir, goldenFiles)
	})
}

func TestCrosGccHostConfig(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		useCCache := false
		cfg, err := getConfig("cros.host", useCCache, oldClangHostWrapperPathForTest, "123")
		if err != nil {
			t.Fatal(err)
		}
		ctx.updateConfig(cfg)

		gomaPath := path.Join(ctx.tempDir, "gomacc")
		ctx.writeFile(gomaPath, "")
		gomaEnv := "GOMACC_PATH=" + gomaPath

		// Note: The old gcc host wrapper is very limited and only adds flags.
		// So we only test very few things here.
		goldenFiles := []goldenFile{
			createGccPathGoldenInputs(ctx, gomaEnv),
			createGoldenInputsForAllTargets("gcc", mainCc),
			createGccArgsGoldenInputs(),
		}

		runGoldenRecords(ctx, crosGccHostGoldenDir, goldenFiles)
	})
}

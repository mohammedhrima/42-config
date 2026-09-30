"""The Android SDK and its emulator.

Unpacking the command-line tools is only half of an Android install: on its own
it gives a directory that `flutter doctor` reports as "Android SDK not found".
The platform, build tools and platform-tools have to be fetched by sdkmanager
afterwards, which is what `setup` does.

The emulator and a system image are another several GB and are only useful if you
actually want to run one, so they are left to `42 avd`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import log
import system

#: Flutter raises the API level it requires over time, so the version comes from
#: ~/42.toml rather than being fixed here.
DEFAULT_API_LEVEL = 36


def base_packages(api: int) -> tuple[str, ...]:
    """Enough for flutter doctor to pass and for a real build to work."""
    return ("platform-tools", f"platforms;android-{api}", f"build-tools;{api}.0.0")


def emulator_packages(api: int) -> tuple[str, ...]:
    """Fetched by `42 avd`, on top of the base packages."""
    return ("emulator", system_image(api))


def system_image(api: int) -> str:
    return f"system-images;android-{api};google_apis;x86_64"


def device_name(api: int) -> str:
    return f"pixel_{api}"


def _sdkmanager(sdk_dir: Path) -> Path:
    return sdk_dir / "cmdline-tools" / "latest" / "bin" / "sdkmanager"


def _accept_licenses(sdk_dir: Path) -> None:
    """sdkmanager refuses to install anything until its licences are accepted."""
    subprocess.run(
        [str(_sdkmanager(sdk_dir)), "--licenses"],
        input="y\n" * 50, text=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )


def _install_packages(sdk_dir: Path, packages: tuple[str, ...]) -> bool:
    """Run sdkmanager, letting its progress reach the terminal."""
    log.info(f"installing: {', '.join(packages)}")
    log.info("this is a few GB and takes a while")
    result = subprocess.run([str(_sdkmanager(sdk_dir)), "--install", *packages],
                            check=False)
    return result.returncode == 0


def setup(sdk_dir: Path, api: int = DEFAULT_API_LEVEL) -> bool:
    """Finish an Android install so the SDK is actually usable."""
    if not _sdkmanager(sdk_dir).is_file():
        log.err("android command-line tools are missing")
        return False

    if (sdk_dir / "platforms" / f"android-{api}").is_dir():
        log.info(f"android SDK {api} already installed")
        return True

    log.info("accepting SDK licences")
    _accept_licenses(sdk_dir)

    if not _install_packages(sdk_dir, base_packages(api)):
        log.err("sdkmanager failed")
        return False

    log.ok("android SDK ready")
    return True


def create_and_start(sdk_dir: Path, avd_home: Path, name: str = "",
                     api: int = DEFAULT_API_LEVEL) -> bool:
    """Create the emulator device if it is missing, then start it."""
    name = name or device_name(api)
    if not _sdkmanager(sdk_dir).is_file():
        log.err("android is not installed. Run: 42 install android")
        return False

    if not (avd_home / f"{name}.avd").is_dir():
        log.step(f"Setting up the emulator: {name}")
        _accept_licenses(sdk_dir)
        if not _install_packages(sdk_dir, emulator_packages(api)):
            log.err("sdkmanager failed")
            return False

        log.info(f"creating device {name}")
        avdmanager = sdk_dir / "cmdline-tools" / "latest" / "bin" / "avdmanager"
        created = subprocess.run(
            [str(avdmanager), "create", "avd", "-n", name, "-k", system_image(api),
             "--device", "pixel"],
            input="no\n", text=True, check=False,
        )
        if created.returncode != 0:
            log.err("avdmanager failed")
            return False
        log.ok(f"{name} created in {avd_home}")
    else:
        log.info(f"{name} already exists")

    # Without KVM the emulator is software-rendered and effectively unusable.
    if system.can_read_write(Path("/dev/kvm")):
        log.info("KVM available, hardware acceleration on")
    else:
        log.err("no access to /dev/kvm, the emulator will be very slow")

    log.step(f"Starting {name}")
    emulator = sdk_dir / "emulator" / "emulator"
    subprocess.Popen([str(emulator), "-avd", name],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    log.ok("emulator started. `flutter devices` will list it shortly")
    return True

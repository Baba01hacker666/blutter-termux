
# B(l)utter-Termux
### Customized by Baba01hacker666 [Doraemon Cyber Team]

Flutter Mobile Application Reverse Engineering Tool by Compiling Dart AOT Runtime. Optimized for Termux and speed.

Currently the application supports only Android libapp.so (arm64 only).
Also the application is currently work only against recent Dart versions.

For high priority missing features, see [TODO](#todo)

## Termux

- Same as Debian but needs NDK. If you do not want NDK, remove the Android library dependency files from `dartsdk`.
- I replaced `std::format` usage with [fmt](https://github.com/fmtlib/fmt.git) to make the project easier to build in Termux.
- Install `fmt`: `pkg install fmt`
- It should work for stable and beta Dart SDK builds. Dev builds are not verified.
- If you hit a Capstone include error, check that Termux exposes the headers:
  ```shell
  pkg-config --cflags capstone
  ```

**OR You can copy paste below command to install all requirements:**
```
pip install requests pyelftools && pkg install -y git cmake ninja build-essential pkg-config libicu capstone fmt
```

> [!NOTE]
> In case you face errors related to `no member named 'format'`, replace all occurrences of `std::format` with `fmt::format`:
>  ```shell
>  find -type f -exec sed -i 's/std::format/fmt::format/g' {} +
>  ```


https://github.com/dedshit/blutter-termux/assets/62318734/b7376844-96b0-4aa0-a395-9009d009132e


## Environment Setup
This application uses C++20 Formatting library. It requires very recent C++ compiler such as g++>=13, Clang>=16.

I recommend Linux. This repo has only been tested on Debian sid/trixie.

### Debian Unstable (gcc 13)
- Install build tools and depenencies
```
apt install python3-pyelftools python3-requests git cmake ninja-build \
    build-essential pkg-config libicu-dev libcapstone-dev libfmt-dev
```

### Windows
- Install git and python 3
- Install latest Visual Studio with "Desktop development with C++" and "C++ CMake tools"
- Install required libraries (libcapstone, libicu4c and fmt)
```
python scripts\init_env_win.py
```
- Start "x64 Native Tools Command Prompt"

### macOS Ventura and Sonoma (clang 16)
- Install XCode
- Install clang 16 and required tools
```
brew install llvm@16 cmake ninja pkg-config icu4c capstone fmt
pip3 install pyelftools requests
```

## Usage
Blutter can analyze Flutter applications in several ways.

### APK File
If you have an `.apk` file. Simply provide the path to the APK file and the output directory as arguments:
```shell
python3 blutter.py path/to/app.apk out_dir
```

### `.so` File(s)
Blutter can also analyze `.so` files directly. This can be done in two ways:

1. **Analyzing `.so` files extracted from an APK:**

    If you have extracted the lib directory from an APK file, you can analyze it using Blutter. Provide the path to the lib directory and the output directory as arguments:
    ```shell
    python3 blutter.py path/to/app/lib/arm64-v8a out_dir
    ```
    > The `blutter.py` will automatically detect the Dart version from the Flutter engine and use the appropriate executable to extract information from `libapp.so`.

2. **Analyzing `libapp.so` with a known Dart version:**

    If you only have `libapp.so` and know its Dart version, you can specify it to Blutter. Provide the Dart version with `--dart-version` option, the path to `libapp.so`, and the output directory as arguments:
    ```shell
    python3 blutter.py --dart-version X.X.X_android_arm64 libapp.so out_dir
    ```
    > Replace `X.X.X` with your lib dart version such as "3.4.2_android_arm64". 


If the Blutter executable for the required Dart version does not exist, the script will automatically checkout the Dart source code and compile it.

## Update
Updates are no longer checked automatically during normal runs.

Use `git pull` manually, or ask the CLI to fast-forward the checkout before execution with `--check-updates`.

You can also force a rebuild of the executable:
```
python3 blutter.py path/to/app/lib/arm64-v8a out_dir --check-updates --rebuild
```

## Output files
- **asm/\*** libapp assemblies with symbols
- **blutter_frida.js** the frida script template for the target application
- **objs.txt** complete (nested) dump of Object from Object Pool
- **pp.txt** all Dart objects in Object Pool


## Directories
- **bin** contains blutter executables for each Dart version in "blutter_dartvm\<ver\>\_\<os\>\_\<arch\>" format
- **blutter** contains source code. need building against Dart VM library
- **build** contains building projects which can be deleted after finishing the build process
- **dartsdk** contains checkout of Dart Runtime which can be deleted after finishing the build process
- **external** contains 3rd party libraries for Windows only
- **packages** contains the static libraries of Dart Runtime
- **scripts** contains python scripts for getting/building Dart


## Generating Visual Studio Solution for Development
I use Visual Studio to delevlop Blutter on Windows. ```--vs-sln``` options can be used to generate a Visual Studio solution.
```
python blutter.py path\to\lib\arm64-v8a build\vs --vs-sln
```

## TODO
- More code analysis
  - Function arguments and return type
  - Some psuedo code for code pattern
- Generate better Frida script
  - More internal classes
  - Object modification
- Obfuscated app (still missing many functions)
- Reading iOS binary
- Input as ipa

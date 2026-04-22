import io
import os
import re
import sys
import zipfile
import zlib
from struct import unpack

import requests
from elftools.elf.elffile import ELFFile

REQUEST_TIMEOUT = 15


class DartInfoError(RuntimeError):
    pass


def request_with_retry(method, url, **kwargs):
    last_error = None
    for _ in range(3):
        try:
            response = requests.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
    raise DartInfoError(f"Request failed for {url}: {last_error}") from last_error

# TODO: support both ELF and Mach-O file
def extract_snapshot_hash_flags(libapp_file):
    with open(libapp_file, 'rb') as f:
        elf = ELFFile(f)
        # find "_kDartVmSnapshotData" symbol
        dynsym = elf.get_section_by_name('.dynsym')
        if dynsym is None:
            raise DartInfoError(f"Missing .dynsym section in {libapp_file}")
        symbols = dynsym.get_symbol_by_name('_kDartVmSnapshotData')
        if not symbols:
            raise DartInfoError(
                f"Cannot find _kDartVmSnapshotData in {libapp_file}"
            )
        sym = symbols[0]
        #section = elf.get_section(sym['st_shndx'])
        if sym['st_size'] <= 128:
            raise DartInfoError(
                f"Unexpected _kDartVmSnapshotData size in {libapp_file}: {sym['st_size']}"
            )
        f.seek(sym['st_value'] + 20)
        snapshot_hash = f.read(32).decode()
        data = f.read(256) # should be enough
        end = data.find(b'\0')
        if end == -1:
            raise DartInfoError(f"Cannot parse snapshot flags in {libapp_file}")
        flags = data[:end].decode().strip().split(' ')
    
    return snapshot_hash, flags


def extract_libflutter_info(libflutter_file):
    with open(libflutter_file, 'rb') as f:
        elf = ELFFile(f)
        machine = elf.header.e_machine
        if machine == 'EM_AARCH64':
            arch = 'arm64'
        elif machine == 'EM_X86_64':
            arch = 'x64'
        elif machine == 'EM_ARM':
            arch = 'arm'
        elif machine == 'EM_386':
            arch = 'x86'
        else:
            raise DartInfoError(f"Unsupported architecture: {machine}")

        section = elf.get_section_by_name('.rodata')
        if section is None:
            raise DartInfoError(f"Missing .rodata section in {libflutter_file}")
        data = section.data()
        
        sha_hashes = re.findall(b'\x00([a-f\\d]{40})(?=\x00)', data)
        #print(sha_hashes)
        # all possible engine ids
        engine_ids = [ h.decode() for h in sha_hashes ]
        if len(engine_ids) != 2:
            found = ", ".join(engine_ids) if engine_ids else "<none>"
            raise DartInfoError(
                f"Expected 2 Flutter engine hashes in {libflutter_file}, found {found}"
            )
        
        # beta/dev version of flutter might not use stable dart version (we can get dart version from sdk with found engine_id)
        # support only stable
        epos = data.find(b' (stable) (')
        if epos == -1:
            dart_version = None
        else:
            pos = data.rfind(b'\x00', 0, epos) + 1
            dart_version = data[pos:epos].decode()
        
    return engine_ids, dart_version, arch, 'android'

def get_dart_sdk_url_size(engine_ids):
    #url = f'https://storage.googleapis.com/dart-archive/channels/stable/release/3.0.3/sdk/dartsdk-windows-x64-release.zip'
    for engine_id in engine_ids:
        url = f'https://storage.googleapis.com/flutter_infra_release/flutter/{engine_id}/dart-sdk-windows-x64.zip'
        try:
            resp = request_with_retry("HEAD", url)
        except DartInfoError:
            continue
        sdk_size = int(resp.headers.get('Content-Length', '0'))
        return engine_id, url, sdk_size
    
    raise DartInfoError(
        "Unable to locate a Dart SDK archive for the detected Flutter engine hashes"
    )

def get_dart_commit(url):
    # in downloaded zip
    # * dart-sdk/revision - the dart commit id of https://github.com/dart-lang/sdk/
    # * dart-sdk/version  - the dart version
    # revision and version zip file records should be in first 4096 bytes
    # using stream in case a server does not support range
    commit_id = None
    dart_version = None
    fp = None
    with request_with_retry("GET", url, headers={"Range": "bytes=0-4096"}, stream=True) as r:
        if r.status_code // 10 == 20:
            x = next(r.iter_content(chunk_size=4096))
            fp = io.BytesIO(x)
    
    if fp is not None:
        while fp.tell() < 4096-30 and (commit_id is None or dart_version is None):
            header = fp.read(30)
            if len(header) < 30:
                break
            #sig, ver, flags, compression, filetime, filedate, crc, compressSize, uncompressSize, filenameLen, extraLen = unpack(fp, '<IHHHHHIIIHH')
            _, _, _, compMethod, _, _, _, compressSize, _, filenameLen, extraLen = unpack('<IHHHHHIIIHH', header)
            filename = fp.read(filenameLen)
            #print(filename)
            if extraLen > 0:
                fp.seek(extraLen, io.SEEK_CUR)
            data = fp.read(compressSize)
            
            # expect compression method to be zipfile.ZIP_DEFLATED
            if compMethod != zipfile.ZIP_DEFLATED:
                raise DartInfoError(
                    f"Unexpected compression method {compMethod} while reading {url}"
                )
            if filename == b'dart-sdk/revision':
                commit_id = zlib.decompress(data, wbits=-zlib.MAX_WBITS).decode().strip()
            elif filename == b'dart-sdk/version':
                dart_version = zlib.decompress(data, wbits=-zlib.MAX_WBITS).decode().strip()
    
    # TODO: if no revision and version in first 4096 bytes, get the file location from the first zip dir entries at the end of file (less than 256KB)
    if commit_id is None or dart_version is None:
        raise DartInfoError(f"Unable to extract Dart revision/version from {url}")
    return commit_id, dart_version

def extract_dart_info(libapp_file: str, libflutter_file: str):
    snapshot_hash, flags = extract_snapshot_hash_flags(libapp_file)
    #print('snapshot hash', snapshot_hash)
    #print(flags)

    engine_ids, dart_version, arch, os_name = extract_libflutter_info(libflutter_file)
    # print('possible engine ids', engine_ids)
    # print('dart version', dart_version)

    dart_revision = None
    if dart_version is None:
        _, sdk_url, _ = get_dart_sdk_url_size(engine_ids)
        # print(engine_id)
        # print(sdk_url)
        # print(sdk_size)

        dart_revision, dart_version = get_dart_commit(sdk_url)
        # print(commit_id)
        # print(dart_version)
        #assert dart_version == dart_version_sdk
    
    # TODO: os (android or ios) and architecture (arm64 or x64)
    return dart_version, snapshot_hash, flags, arch, os_name, dart_revision


if __name__ == "__main__":
    libdir = sys.argv[1]
    libapp_file = os.path.join(libdir, 'libapp.so')
    libflutter_file = os.path.join(libdir, 'libflutter.so')

    print(extract_dart_info(libapp_file, libflutter_file))

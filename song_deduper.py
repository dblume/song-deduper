#!/usr/bin/env python3
from __future__ import annotations
import os
import os.path
import sys
import platform
import time
import mutagen   # python3 -m pip install mutagen
from mutagen import easyid3
import acoustid  # python3 -m pip install pyacoustid
import glob
import pickle
import hashlib
from argparse import ArgumentParser
from dataclasses import dataclass
from collections.abc import Sequence
from collections import defaultdict

@dataclass(frozen=True)
class MusicData:
    artist: str
    album: str
    title: str
    genre: str
    year: int
    disc_num: int
    disc_total: int
    track_num: int
    track_total: int
    fingerprint: tuple[float, Sequence[bytes]]
    md5: str


def musicdata_from_eyed3(f, fingerprint, md5) -> MusicData:
    if hasattr(f, 'tag') and f.tag is not None:
        print(f'Artist:{f.tag.artist} Album:{f.tag.album} Title:{f.tag.title} Genre:{f.tag.genre} ({f.tag.track_num.count}/{f.tag.track_num.total})')
        year = f.tag.getBestDate() and f.tag.getBestDate().year or None
        return MusicData(f.tag.artist, f.tag.album, f.tag.title, f.tag.genre, year,
                         f.tag.disc_num.count, f.tag.disc_num.total, f.tag.track_num.count, f.tag.track_num.total, fingerprint, md5)
    return MusicData(None, None, None, None, None, None, None, None, None, fingerprint, md5)


def musicdata_from_easyid3(m, fingerprint, md5) -> MusicData:
    try:
        artist = m["artist"][0]
    except KeyError:
        artist = None
    try:
        album = m["album"][0]
    except KeyError:
        album = None
    try:
        title = m["title"][0]
    except KeyError:
        title = None
    try:
        year = m["date"][0].isdigit() and int(m["date"][0][:4]) or None
    except KeyError:
        year = None
    try:
        genre = m["genre"][0]
    except KeyError:
        genre = None
    print(f'MP3 Artist:{artist} Album:{album} Title:{title}')
    try:
        if m["discnumber"][0].isdigit():
            disc_num = int(m["discnumber"][0])
            disc_total = None
        elif '/' in m["discnumber"][0]:
            disc_num, disc_total = [int(i) for i in m["discnumber"][0].split('/', 1)]
        else:
            disc_num = disc_total = None
    except KeyError:
        disc_num = disc_total = None
    try:
        if m["tracknumber"][0].isdigit():
            track_num = int(m["tracknumber"][0])
            track_total = None
        elif '/' in m["tracknumber"][0]:
            track_num, track_total = [int(i) for i in m["tracknumber"][0].split('/', 1)]
        else:
            track_num = track_total = None
    except KeyError:
        track_num = track_total = None
    return MusicData(artist, album, title, genre, year, disc_num, disc_total,
                     track_num, track_total, fingerprint, md5)


def musicdata_from_m4a(m, fingerprint, md5) -> MusicData:
    try:
        artist = m.tags['\xa9ART'][0]
    except KeyError:
        artist = None
    try:
        album = m.tags['\xa9alb'][0]
    except KeyError:
        album = None
    try:
        title = m.tags['\xa9nam'][0]
    except KeyError:
        title = None
    try:
        genre = m.tags['\xa9gen'][0]
    except KeyError:
        genre = None
    print(f'MP4 Artist:{artist} Album:{album} Title:{title}')
    try:
        year = m.tags['\xa9day'][0].isdigit() and int(m.tags['\xa9day'][0][:4]) or None
    except KeyError:
        year = None
    try:
        disc_num, disc_total = m.tags['disk'][0]
    except KeyError:
        disc_num = disc_total = None
    try:
        track_num, track_total = m.tags['trkn'][0]
    except KeyError:
        track_num = track_total = None
    return MusicData(artist, album, title, genre, year, disc_num, disc_total,
           track_num, track_total, fingerprint, md5)


def md5(fname: str) -> str:
    """Return an MD5 hash for the provided file"""
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        #for chunk in iter(lambda: f.read(8192), b""):  # for Python < 3.8
        while chunk := f.read(8192):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def glob_cache(path: str, fname_prefix: str) -> Sequence[str]:
    """Try to read a pickle file of filenames"""
    files = []
    fname = fname_prefix + 'glob_cache.pickle'
    try:
        with open(fname, 'rb') as f:
            files = pickle.load(f)
    except FileNotFoundError:
        for f in glob.glob(path + '/**', recursive=True):
            if f.endswith('.mp3') or f.endswith('.m4a'):
                files.append(f)
        files.sort()
        with open(fname, 'wb') as f:
            pickle.dump(files, f)
    return files


def get_music_datas(path: str, fname_prefix: str) -> Dict[str, MusicData]:
    """Try to read a pickle file of filename to MusicData"""
    fname = fname_prefix + 'music_datas.pickle'
    d = {}
    try:
        with open(fname, 'rb') as f:
            d = pickle.load(f)
    except FileNotFoundError:
        files = glob_cache(path, fname_prefix)
        count = 0
        for fn in files:
            if os.path.exists(fn):
                md5_ = md5(fn)
                fingerprint = acoustid.fingerprint_file(fn)
                if fn.lower().endswith('.mp3'):
                    f = mutagen.easyid3.EasyID3(fn)
                    md = musicdata_from_easyid3(f, fingerprint, md5_)
                elif fn.lower().endswith('.m4a'):
                    f = mutagen.File(fn)
                    md = musicdata_from_m4a(f, fingerprint, md5_)

                # This was the eyed3 way:
                #f = eyed3.load(fn)
                #md = musicdata_from_eyed3(f, fingerprint, md5_)
                d[fn] = md
                count += 1
        with open(fname, 'wb') as f:
            pickle.dump(d, f)
    return d


def process_music_datas(music_datas: Dict) -> None:
    hashes = defaultdict(list)
    tags = defaultdict(list)
    for fname, info in music_datas.items():
        hashes[info.md5].append(fname)
        tags[(info.artist, info.title)].append(fname)

    print_dupes(hashes, music_datas)
    print_dupes(tags, music_datas)


def print_dupes(dupes_dict: Dict, music_datas: Dict) -> None:
    for k, fnames in dupes_dict.items():
        if len(fnames) == 1:
            continue
        print(f"\nSame Key {k}:")
        prev_fingerprint = None
        for fname in fnames:
            # TODO: Also compare other keys, like album, track number?
            if prev_fingerprint is None:
                print(f"---- {fname}")
            else:
                similarity = acoustid.compare_fingerprints(prev_fingerprint,
                                 music_datas[fname].fingerprint[1])
                print(f"{similarity:1.2f} {fname}")
            prev_fingerprint = music_datas[fname].fingerprint[1]


def main(path: str, debug: bool, fname_prefix: str) -> None:
    music_datas = get_music_datas(path, fname_prefix)
    process_music_datas(music_datas)

#    other_platform = platform.system() == 'Darwin' and 'pc_music_datas.pickle' or 'mac_music_datas.pickle'
#    with open(other_platform, 'rb') as f:
#        op_music_datas = pickle.load(f)
#        process_music_datas(op_music_datas)


if __name__ == '__main__':
    parser = ArgumentParser(description='Just a template sample.')
    parser.add_argument('-d', '--debug', action='store_true')
    if platform.system() == 'Darwin':
        parser.add_argument('path', default='/Users/david/Music', nargs='?')
        fname_prefix = "mac_"
    else:
        parser.add_argument('path', default='/mnt/d/backup_from_lenovo/Users/David/Music', nargs='?')
        fname_prefix = "pc_"
    args = parser.parse_args()
    main(args.path, args.debug, fname_prefix)

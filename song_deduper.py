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
from typing import Optional

pickle_filename = 'music_datas.pickle'


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


def has_supported_file_extension(filename: str) -> bool:
    return filename[-4:].lower() in ('.mp3', '.m4a')


def glob_cache(path: str, fname_prefix: str) -> Sequence[str]:
    """Try to read a pickle file of filenames.
    If it doesn't exist, create one."""
    files = []
    fname = fname_prefix + 'glob_cache.pickle'
    try:
        with open(fname, 'rb') as f:
            files = pickle.load(f)
    except FileNotFoundError:
        for f in glob.glob(path + '/**', recursive=True):
            if has_supported_file_extension(f):
                files.append(f)
        files.sort()
        with open(fname, 'wb') as f:
            pickle.dump(files, f)
    return files


def add_song_to_musicdata(song_file:str, music_datas:Dict[str, MusicData]) -> None:
    """Create a MusicData from the song_file, add it to the dict."""
    md5_ = md5(song_file)
    fingerprint = acoustid.fingerprint_file(song_file)
    if song_file.lower().endswith('.mp3'):
        f = mutagen.easyid3.EasyID3(song_file)
        md = musicdata_from_easyid3(f, fingerprint, md5_)
    elif song_file.lower().endswith('.m4a'):
        f = mutagen.File(song_file)
        md = musicdata_from_m4a(f, fingerprint, md5_)
    music_datas[song_file] = md


def get_music_datas(path: str, fname_prefix: str) -> Dict[str, MusicData]:
    """Try to read a pickle file of a dict filename:MusicData
    If there's no pickle file, make a new one."""
    fname = fname_prefix + pickle_filename
    musicdata = {}
    try:
        with open(fname, 'rb') as f:
            musicdata = pickle.load(f)
    except FileNotFoundError:
        files = glob_cache(path, fname_prefix)
        for song_file in files:
            add_song_to_musicdata(song_file, musicdata)
        with open(fname, 'wb') as f:
            pickle.dump(musicdata, f)
    return musicdata


def delete_files(fname: str, music_datas: Dict[str, MusicData]) -> bool:
    """Given a filename of a file with a list of mp3s or m4as to delete,
    delete them and also remove them from the music_datas dict.
    Return whether an updated music_datas needs to be written to disk."""
    changed = False
    for line in open(fname):
        fname = line.strip()
        if os.path.isfile(fname) and has_supported_file_extension(fname):
            os.unlink(fname)
        else:
            print(f'Warn: Did not try to delete {fname}', file=sys.stderr)

        if fname in music_datas:
            del music_datas[fname]
            changed = True
        else:
            print(f'Warn: Not in MusicData: {fname}', file=sys.stderr)
    return changed


def process_music_datas(music_datas: Dict[str, MusicData]) -> None:
    hashes = defaultdict(list)
    tags = defaultdict(list)
    for fname, info in music_datas.items():
        hashes[info.md5].append(fname)
        tags[(info.artist, info.title)].append(fname)

    print_dupes(hashes, music_datas)
    print_dupes(tags, music_datas)


def print_dupes(dupes_dict: Dict, music_datas: Dict[str, MusicData]) -> None:
    for k, fnames in dupes_dict.items():
        if len(fnames) == 1:
            continue
        print(f"\nSame {k}:")
        prev_fingerprints = []
        for fname in fnames:
            # TODO: Also compare other keys, like album, track number?
            for fp in prev_fingerprints:
                similarity = acoustid.compare_fingerprints(fp,
                                 music_datas[fname].fingerprint[1])
                print(f"{similarity:1.2f} ", end='')
            print('---- ' * (len(fnames) - len(prev_fingerprints) - 1), end='')
            print(fname)
            prev_fingerprints.append(music_datas[fname].fingerprint[1])


def find_missing_songs(op_music_datas: Dict[str, MusicData], music_datas: Dict[str, MusicData]) -> None:
    """See what songs are on the other platform but not on this one"""
    tags = defaultdict(list)
    tags_set = set()
    for fname, info in music_datas.items():
        tags[(info.artist, info.title)].append(fname)
        tags_set.add((info.artist, info.title))
    op_tags = defaultdict(list)
    op_tags_set = set()
    for fname, info in op_music_datas.items():
        op_tags[(info.artist, info.title)].append(fname)
        op_tags_set.add((info.artist, info.title))
    diff = op_tags_set - tags_set
    for i in diff:
        print(f'Missing: {i}: {op_tags[i]}')


def main(path: str, files_to_delete: Optional[str], fname_prefix: str) -> None:
    music_datas = get_music_datas(path, fname_prefix)
    if (files_to_delete):
        if delete_files(files_to_delete, music_datas):
            fname = fname_prefix + pickle_filename
            os.rename(fname, fname + '.old')
            with open(fname, 'wb') as f:
                pickle.dump(music_datas, f)
    process_music_datas(music_datas)

    # Optional, if you want to compare with a remote collection
    other_platform = platform.system() == 'Darwin' and 'pc_music_datas.pickle' or 'mac_music_datas.pickle'
    with open(other_platform, 'rb') as f:
        op_music_datas = pickle.load(f)
        process_music_datas(op_music_datas)
        find_missing_songs(op_music_datas, music_datas)


if __name__ == '__main__':
    parser = ArgumentParser(description='Finds duplicate songs and helps delete them.')
    parser.add_argument('-d', '--deletefile', help='Delete the filenames in the specified file.')
    if platform.system() == 'Darwin':
        parser.add_argument('path', default='/Users/david/Music', nargs='?',
                            help='Path to directory containing song hiearchy.')
        fname_prefix = "mac_"
    else:
        parser.add_argument('path', default='/mnt/d/backup_from_lenovo/Users/David/Music', nargs='?',
                            help='Path to directory containing song hiearchy.')
        fname_prefix = "pc_"
    args = parser.parse_args()
    main(args.path, args.deletefile, fname_prefix)

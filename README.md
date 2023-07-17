[![Code Climate](https://codeclimate.com/github/dblume/song-deduper/badges/gpa.svg)](https://codeclimate.com/github/dblume/song-deduper)
[![Issue Count](https://codeclimate.com/github/dblume/song-deduper/badges/issue_count.svg)](https://codeclimate.com/github/dblume/song-deduper/issues)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://raw.githubusercontent.com/dblume/song-deduper/main/LICENSE.txt)
![python3.x](https://img.shields.io/badge/python-3.x-green.svg)

## Song De-Duper

Miscellaneous functions to de-duplicate songs. It uses the same fingerprints used by [MusicBrainz](https://musicbrainz.org/)
and does similar de-duplication to that of [Beets](https://beets.io/).

    $ ./song_deduper.py --help
    usage: song_deduper.py [-h] [-d DELETEFILE] [path]
    
    Finds duplicate songs and helps delete them.
    
    positional arguments:
      path                  Path to directory containing song hiearchy.
    
    optional arguments:
      -h, --help            show this help message and exit
      -d DELETEFILE, --deletefile DELETEFILE
                            Delete the filenames in the specified file.

## Example Use

Run it on your music collection, like so:

    ./song_deduper.py /music

And it'll print out which files are probably dupes. Here's three such files:

    Same ('Fiona Apple', 'Across The Universe'):
    ---- ---- /music/Fiona Apple - Across the Universe.mp3
    0.67 ---- /music/Google Play/Fiona Apple/Pleasantville -Music From The/01 Across The Universe.mp3
    1.00 0.67 /music/iTunes/Fiona Apple/When the Pawn Hits/11 Across The Universe.mp3

The above three files matched on artist and song. The first one starts with "---- ----" meaning no fingerprints were compared yet.
The second one starts with "0.67 ----" meaning it's a near match for the first one, but was not compared to the third one yet.
The third one starts with "1.00 0.67" meaning it's a dupe of the first one, and only a near match for the second one.

The truth is, the second file was a close enough match to delete too.

If you made a file full of pathnames to songs to delete, you can send it to song\_deduper to remove them and to 
remove them from the database (so you don't have to rebuild it from scratch).

    ./song_deduper.py --deletefile pathnames_to_songs_to_delete.txt

## Getting Started

There are two main ways to setup dependencies. Either:

- Install the fpcalc CLI executable, and the chromaprint Python script will invoke it. This is easier to setup.
- Install the libraries needed from source, and the chromaprint Python script will use them in-process.

### The easier to setup option: Use fpcalc CLI

#### 1. Install fpcalc (the executable)

Install [Chromaprint's fpcalc](https://acoustid.org/chromaprint) to get an executable
that makes audio fingerprints.

On macOS, you can download the executable, or brew install it.

#### 2. Install Python Modules

You may want to do this in a virtual environment (venv).

    python3 -m pip install pyacoustid mutagen

[Pyacoustid](https://github.com/beetbox/pyacoustid) is a wrapper around Chromaprint,
and won't work if you don't install Chromaprint or fpcalc too. In our case, we're going to use `fpcalc`.

You can't compare fingerprints with fpcalc, though. You need chromaprint for that.

[Mutagen](https://github.com/quodlibet/mutagen) reads and writes tags on MP3 and M4A
files. I started with [EyeD3](https://github.com/nicfit/eyeD3) but it only works with
MP3 files.

#### 3. Test acoustid and fpcalc with aidmatch.py

Use environment variable `FPCALC` so acoustid will know which engine to use.
"aidmatch.py" is a test script to ensure the installation went OK.

    FPCALC=chromaprint-fpcalc/fpcalc python3 aidmatch.py "Peaches.mp3"

### The harder option: Build dependencies locally

- Install [FFTW](https://www.fftw.org/download.html) for chromaprint. (`brew install fftw` for macOS)
- Install [ffmpeg audio-only](https://github.com/acoustid/ffmpeg-build) (go to releases) or build from source [ffmpeg](https://ffmpeg.org/download.html) for chromaprint.
- Get the [chromaprint source-code tarball](https://acoustid.org/chromaprint).

Then in chromaprint-1.5.1 (or current version) on a Macintosh, for example:

    FFMPEG_DIR=ffmpeg-5.1.2-audio-x86_64-apple-macos10.9/ cmake .
    make

Note that [chromaprint can be configured to use different FFT libraries](https://github.com/acoustid/chromaprint#fft-library).

Or, on Ubuntu:

    sudo apt-get install libavcodec-dev
    sudo apt-get install libavformat-dev
    cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_TOOLS=ON .
    make
    sudo make install

## Is it any good?

[Yes](https://news.ycombinator.com/item?id=3067434).

## Licence

This software uses the [MIT License](https://raw.githubusercontent.com/dblume/song-deduper/main/LICENSE.txt)

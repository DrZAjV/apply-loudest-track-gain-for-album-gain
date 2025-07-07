# apply-loudest-track-gain-for-album-gain

# Background:
https://www.aes.org/technical/documentDownloads.cfm?docID=731

# Required:

rsgain

python-3.13.1

pip3 install mutagen



# Usage:

Step 1:

rsgain easy -mMax -O -p <your_profile> <your_music_library>

Step 2:

apply_loudest_track_gain.py <your_music_library>

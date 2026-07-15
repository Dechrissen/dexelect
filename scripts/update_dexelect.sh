#!/bin/sh

# Update script for dexelect.derekandersen.net

now=$(date +"%H-%M-%S_%m_%d_%Y")
sudo systemctl stop dexelect.service
cd /home/derek/apps/dexelect
git reset --hard -q
git pull -q
.venv/bin/pip install -r requirements.txt --quiet
.venv/bin/python main.py --fetch-sprites
sudo systemctl start dexelect.service
echo "$now updated" >> /home/derek/dexelect.log
sleep 1
echo "dexelect.derekandersen.net successfully updated!"
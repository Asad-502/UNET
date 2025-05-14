#!/bin/bash

# Create Directories
mkdir weights
mkdir datasets

# Download the datasets
cd datasets
kaggle datasets download -d andrewmvd/drive-digital-retinal-images-for-vessel-extraction
wget -O stare.zip https://cecas.clemson.edu/~ahoover/stare/images/all-images.zip
wget -O hrf.zip https://www5.cs.fau.de/fileadmin/research/datasets/fundus-images/all.zip
wget -O Chase.zip https://researchdata.kingston.ac.uk/96/1/CHASEDB1.zip

# Extract the datasets
unzip -o drive-digital-retinal-images-for-vessel-extraction.zip -d drive-digital-retinal-images
unzip -o stare.zip -d stare

unzip -o hrf.zip -d hrf
unzip -o Chase.zip -d Chase

# Remove the archive files
rm drive-digital-retinal-images-for-vessel-extraction.zip
rm stare.zip
rm hrf.zip
rm Chase.zip

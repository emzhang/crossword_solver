# Use wget to download puz files from the internet archive.
# i.e wget https://archive.org/download/nyt-puz/daily/1993/11/Nov2193.puz


import os
import sys
import time
import subprocess

import requests
from bs4 import BeautifulSoup


for year in range(2021, 2022):
    for month_num, month_word in [
        (1, "Jan"),
        (2, "Feb"),
        (3, "Mar"),
        (4, "Apr"),
        (5, "May"),
        (6, "Jun"),
        (7, "Jul"),
        (8, "Aug"),
        (9, "Sep"),
        (10, "Oct"),
        (11, "Nov"),
        (12, "Dec"),
    ]:
        # List all urls on this url
        url = f"https://archive.org/download/nyt-puz/daily/{year}/{month_num:02}/"
        print(url)
        # url = "https://archive.org/download/nyt-puz/daily/1993/11/"
        reqs = requests.get(url)
        soup = BeautifulSoup(reqs.text, "html.parser")
        urls = []

        for link in soup.find_all("a"):
            href = link.get("href")
            if href and href.endswith(".puz"):
                urls.append(f"{url}/{href}")

        for url in urls:
            filename = f'data/{year}/{month_num}/{url.split("/")[-1]}'

            # check if the directory exists and create it if it doesn't
            directory = os.path.dirname(filename)
            if not os.path.exists(directory):
                os.makedirs(directory)

            if not os.path.exists(filename):
                print(f"Downloading {url} to {filename}")
                subprocess.run(["wget", url, "-O", filename])
            else:
                print(f"Skipping {url} to {filename}")

            # print(url)
            # filename = f"{year}-{month:02d}-{day:02d}.puz"
            # if not os.path.exists(filename):
            #     print(f"Downloading {url} to {filename}")
            #     subprocess.run(["wget", url, "-O", filename])
            #     time.sleep(1)
            # else:
            #     print(f"Skipping {url} to {filename}")

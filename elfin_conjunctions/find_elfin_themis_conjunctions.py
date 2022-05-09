
from datetime import datetime
import pathlib

import pandas as pd
import numpy as np
import asilib

from elfin_conjunctions.elfin_footprint import Elfin_footprint
from elfin_conjunctions.load.elfin import load_epd
from elfin_conjunctions import config

themis_imagers = asilib.themis_info()
themis_url = 'https://data.phys.ucalgary.ca/sort_by_project/THEMIS/asi/stream0/'


save_dir = pathlib.Path(config['project_dir'] / 'data' / 'conjunctions')
if not save_dir.exists():
    save_dir.mkdir(parents=True)
    print(f'Made {save_dir} directory.')

for sc_id in ['a', 'b']:
    days = pd.date_range(start='2018-01-01', end=datetime.now(), freq='D')
    for day in days:
        # Look for an EPD file and skip the day if none exists.
        try:
            epd_time, epd = load_epd(sc_id, day)
        except (FileNotFoundError, ValueError) as err:
            if 'EPD files found at' in str(err):
                continue
            if 'No records found for variable' in str(err):
                print(f'No data on day {day.date()}')
                continue
            else:
                raise

        # Calculate the ELFIN footprints in the LLA coordinates.
        footprint = Elfin_footprint(sc_id, day)
        footprint.map_footprint()

        # What ASI was below ELFIN?
        for location_code in themis_imagers['location_code']:
            imager = asilib.themis(location_code, time=day, load_images=False)
            c2 = asilib.Conjunction(imager, footprint.time, footprint.lla)
            conjunction_df = c2.find()
            conjunction_df['epd_data'] = False
            conjunction_df['asi_data'] = False

            for index, row in conjunction_df.iterrows():
                # Was there EPD data at this time?
                idx = np.where(
                    (epd_time > row['start']) &
                    (epd_time < row['end'])
                )[0]
                if len(idx):
                    conjunction_df.loc[index, 'epd_data'] = True

                # Was there ASI data at this time?
                download = asilib.io.download.Downloader(themis_url)
                url_subdirectories = [
                    str(day.year), 
                    str(day.month).zfill(2), 
                    str(day.day).zfill(2), 
                    f'{location_code.lower()}*', 
                    f'ut{str(row["start"].hour).zfill(2)}', 
                    ]
                filename = row["start"].strftime(f'%Y%m%d_%H%M_{location_code.lower()}*.pgm.gz')
                try:
                    asi_url = download.find_url(subdirectories=url_subdirectories, filename=filename)
                except FileNotFoundError as err:
                    if 'does not contain any hyper references containing' in str(err):
                        continue
                conjunction_df.loc[index, 'asi_data'] = True
                
                # Save to file.
                save_name = f'elfin_{sc_id.lower()}_themis_{location_code.lower()}_conjunctions.csv'
                
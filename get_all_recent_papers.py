import ads_query
import datetime
import pandas as pd

orcids = pd.read_csv("data/orcids.csv")["orcid"].values
last_names = pd.read_csv("data/orcids.csv")["last_name"].values

for orcid, last_name in zip(orcids, last_names):
    papers_dict_list = ads_query.get_ads_papers(query=f"orcid:{orcid}", remove_known_papers=True)

    # recent_papers = [paper for paper in papers_dict_list if paper["date"] > datetime.date(2023, 8, 1)]

    print(f"Found {len(papers_dict_list)} papers for {last_name}")

    ads_query.save_papers(papers_dict_list)

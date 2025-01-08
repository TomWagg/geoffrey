import ads
import datetime
import pandas as pd
import numpy as np
from unidecode import unidecode
from collections import defaultdict

def get_ads_papers(query, astronomy_collection=True, past_week=False, allowed_types=["article", "eprint"],
                   remove_known_papers=False):
    """Get papers from NASA/ADS based on a query

    Parameters
    ----------
    query : `str`
        Query used for ADS searchs
    astronomy_collection : `bool`, optional
        Whether to restrict to the astronomy collection, by default True
    past_week : `bool`, optional
        Whether to restrict to papers from the past week, by default False
    allowed_types : `list`, optional
        List of allowed types of papers, by default ["article", "eprint"]
    """
    # append astronomy collection to query if wanted
    if astronomy_collection:
        query += " collection:astronomy"

    # if in the past week
    if past_week:
        # use datetime to work out the dates
        today = datetime.date.today()
        week_ago = today - datetime.timedelta(weeks=4)

        # restrict the entdates to the date range of last week
        query += f" entdate:[{week_ago.strftime('%Y-%m-%d')} TO {today.strftime('%Y-%m-%d')}]"

    # get the papers
    papers = ads.SearchQuery(q=query, sort="date", fl=["abstract", "author", "citation_count", "doctype",
                                                       "first_author", "read_count", "title", "bibcode",
                                                       "pubdate", "keyword", 'pub'])

    papers_dict_list = []

    for paper in papers:
        if paper.doctype in allowed_types:
            year, month, _ = map(int, paper.pubdate.split("-"))
            papers_dict_list.append({
                "link": f"https://ui.adsabs.harvard.edu/abs/{paper.bibcode}/abstract",
                "title": paper.title[0],
                "abstract": paper.abstract,
                "authors": paper.author,
                "date": datetime.date(year=year, month=month, day=1),
                "citations": paper.citation_count,
                "reads": paper.read_count,
                "keywords": paper.keyword,
                "publisher": paper.pub
            })
    if remove_known_papers:
        papers_dict_list = filter_known_papers(papers_dict_list)
    return papers_dict_list


def check_uw_authors(paper, uw_authors):
    """Check if the authors of a paper are from UW

    Parameters
    ----------
    paper : `dict`
        Dictionary of paper information
    uw_authors : `dict`
        Dictionary of UW authors with last name as key and first initial as value

    Returns
    -------
    first_author : `bool`
        Whether the first author is from UW
    total_uw : `int`
        Total number of UW authors
    """
    first_author, total_uw = False, 0
    for i, author in enumerate(paper['authors']):
        if author.count(",") != 1:
            continue
        last, first = author.split(", ")
        initial = first[0].lower()
        last = unidecode(last).lower()

        if last in uw_authors and initial in uw_authors[last]:
            if i == 0:
                first_author = True
            total_uw += 1
    return first_author, total_uw


def filter_known_papers(papers_dict_list):
    papers = pd.read_csv("data/papers.csv")
    known_papers = papers['title'].values
    new_papers = []
    for paper in papers_dict_list:
        if paper['title'] not in known_papers:
            new_papers.append(paper)
    return new_papers


def get_uw_authors():
    # read in the UW authors
    uw_authors_table = pd.read_csv("data/orcids.csv")
    uw_authors = defaultdict(list)
    for _, row in uw_authors_table.iterrows():
        uw_authors[row['last_name'].lower()].append(row['first_name'][0].lower())

    # HACK: add David and Chester's alternate names
    uw_authors["wang"].append("y")
    uw_authors["li"].append("z")
    return uw_authors


def save_papers(papers_dict_list):
    """Save papers to a CSV file

    Parameters
    ----------
    papers_dict_list : `list`
        List of dictionaries of paper information
    """
    uw_authors = get_uw_authors()

    for i in range(len(papers_dict_list)):
        papers_dict_list[i]["first_author"] = papers_dict_list[i]["authors"][0]

    # create a dictionary of the data    
    df_dict = {key: [i[key] for i in papers_dict_list]
               for key in ['title','first_author','authors','date','publisher','keywords','link','abstract']}

    # initialize the first author and total UW authors
    uw_first_author = np.repeat(False, len(papers_dict_list))
    total_uw = np.zeros(len(papers_dict_list)).astype(int)

    # go through each paper and check UW authors
    for i, paper in enumerate(papers_dict_list):
        uw_first_author[i], total_uw[i] = check_uw_authors(paper, uw_authors)

    # add the first author and total UW authors to the dictionary
    df_dict['uw_first_author'] = uw_first_author
    df_dict['total_uw'] = total_uw

    # read in the current papers and add the new ones
    df = pd.read_csv("data/papers.csv")
    new_df = pd.DataFrame(df_dict)
    df = pd.concat([df,new_df])
    df.to_csv("data/papers.csv", index=False)


def bold_uw_authors(author_string, uw_authors=None):
    """Bold the uw authors in the list of authors

    Parameters
    ----------
    author_string : `str`
        Initial author string
    name : `str`
        Name of grad

    Returns
    -------
    authors: `str`
        Author string but with asterisks around the grad
    """
    authors = "_Authors: "

    if uw_authors is None:
        uw_authors = get_uw_authors()

    # go through each author in the list
    for author in author_string:
        if author.count(",") != 1:
            continue
        split_author = list(reversed(author.split(", ")))
        first, last = split_author
        initial = first[0].lower()
        last = unidecode(last).lower()

        # NOTE: I assume if first initial and last name match then it is the right person
        if last in uw_authors and initial in uw_authors[last]:
            # add asterisks for bold in mrkdwn
            authors += f"*{' '.join(split_author)}*, "
        else:
            authors += f"{' '.join(split_author)}, "

    # add final underscore so the whole thing is italic
    authors = authors[:-2] + "_"
    return authors

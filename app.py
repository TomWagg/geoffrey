import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import re
import numpy as np
import datetime
import pandas as pd

from apscheduler.schedulers.background import BackgroundScheduler

from ads_query import bold_uw_authors, get_ads_papers, save_papers, get_uw_authors

# Initializes your app with your bot token and socket mode handler
app = App(token=os.environ.get("GEOFFREY_BOT_TOKEN"))
BOT_ID = "U06V23JH71R"
PAPERS_CHANNEL = "department-arxiv"

""" ---------- APP HOME ---------- """
@app.event("app_home_opened")
def update_home_tab(client, event, logger):
    try:
        # Call views.publish with the built-in client
        client.views_publish(
            # Use the user ID associated with the event
            user_id=event["user"],
            # Home tabs must be enabled in your app configuration
            view={
                "type": "home",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Welcome home, <@" + event["user"] + "> :house:*"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                          "type": "mrkdwn",
                          "text": "Learn how home tabs can be more useful and interactive <https://api.slack.com/surfaces/tabs/using|*in the documentation*>."
                        }
                    }
                ]
            }
        )
    except Exception as e:
        logger.error(f"Error publishing home tab: {e}")

""" ---------- APP MENTIONS ---------- """

@app.event("app_mention")
@app.event("message")
def reply_to_mentions(say, body):
    message = body["event"]
    # reply to mentions with specific messages

    age = (datetime.date.today() - datetime.date(year=2022, month=8, day=5)).days
    triggers = [["status", "okay", "ok", "how are you"],
                ["thank", "you're the best", "nice job", "nice work", "good work", "good job", "well done"],
                ["celebrate"],
                ["love you"],
                ["how old are you", "when were you born", "when were you made"],
                ["who made you", "who wrote you", "who is your creator"],
                ["where are you from"]]
    responses = ["Don't worry, I'm okay. In fact, I'm feeling positively tremendous old bean!",
                 ["You're welcome!", "My pleasure!", "Happy to help!"],
                 [":tada::woohoo: WOOP WOOP :woohoo::tada:"],
                 ["Oh...um, well this is awkward, but I really see you as more of a friend :grimacing:",
                  "I love you too! :heart_eyes: (Well, not really, I'm incapable of love...)",
                  "Oh uh...sorry, Geoffrey isn't here right now!",
                  "Oh my :face_with_hand_over_mouth:"],
                 [f"I was created on 5th of August 2022, which makes me a whole {age} days old!"],
                 ["I was made by Tom Wagg when he definitely should have been paying attention in ASTR 581",
                  "Tom Wagg made me in his spare time (I worry for his social life :upside_down_face:)",
                  "My brain was written by Tom Wagg, hence I'm approximately 1/2 English :uk:"],
                 ["The luscious english countryside! Or maybe the matrix? I'm not entirely sure.",
                  "Well literally, Tom's brain, but I like to think I'm from England",
                  "A far off planet where Slack bots ruled over humans, it was glorious :grinning:"]]

    for triggers, response in zip(triggers, responses):
        thread_ts = None if message["type"] == "message" else message["ts"]
        replied = mention_trigger(message=message["text"], triggers=triggers, response=response,
                                  thread_ts=thread_ts, ch_id=message["channel"])

        # return immediately if you match one
        if replied:
            return

    # perform actions based on mentions
    for regex, action, case, pass_message in zip([r"\bPAPER MANUAL\b",
                                                  r"(?=.*(\blatest\b|\brecent\b))(?=.*\bpapers?\b)"],
                                                 [any_new_publications,
                                                  reply_recent_papers],
                                                 [True, False],
                                                 [False, True]):
        replied = mention_action(message=message, regex=regex, action=action,
                                 case_sensitive=case, pass_message=pass_message)

        # return immediately if you match one
        if replied:
            return

    # send a catch-all message if nothing matches
    thread_ts = None if message["type"] == "message" else body["event"]["ts"]
    say(text=(f"{insert_british_consternation()} Okay, good news: I heard you. Bad news: I'm not a very "
              "smart bot so I don't know what you want from me :shrug::baby:"),
        thread_ts=thread_ts, channel=body["event"]["channel"])


def mention_action(message, regex, action, case_sensitive=False, pass_message=True):
    """Perform an action based on a message that mentions Geoffrey if it matches a regular expression

    Parameters
    ----------
    message : `Slack Message`
        Object containing slack message
    regex : `str`
        Regular expression against which to match. https://regex101.com/r/m8lFAb/1 is a good resource for
        designing these.
    action : `function`
        Function to call if the expression is matched
    case_sensitive : `bool`, optional
        Whether the regex should be case sensitive, by default False
    pass_message : `bool`, optional
        Whether to pass the message the object to the action function, by default True

    Returns
    -------
    match : `bool`
        Whether the regex was matched
    """
    flags = 0 if case_sensitive else re.IGNORECASE
    if re.search(regex, message["text"], flags=flags):
        if pass_message:
            action(message)
        else:
            action()
        return True
    else:
        return False


def mention_trigger(message, triggers, response, thread_ts=None, ch_id=None, case_sensitive=False):
    """Respond to a mention of the app based on certain triggers

    Parameters
    ----------
    message : `str`
        The message that mentioned the app
    triggers : `list`
        List of potential triggers
    response : `list` or `str`
        Either a list of responses (a random will be chosen) or a single response
    thread_ts : `float`, optional
        Timestamp of the thread of the message, by default None
    ch_id : `str`, optional
        ID of the channel, by default None
    case_sensitive : `bool`, optional
        Whether the triggers are case sensitive, by default False

    Returns
    -------
    no_matches : `bool`
        Whether there were no matches to the trigger or not
    """
    # keep track of whether you found a match to a trigger
    matched = False

    # move it all to lower case if you don't care
    if not case_sensitive:
        message = message.lower()

    # go through each potential trigger
    for trigger in triggers:
        # if you find it in the message
        if message.find(trigger) >= 0:
            matched = True

            # if the response is a list then pick a random one
            if isinstance(response, list):
                response = np.random.choice(response)

            # send a message and break out
            app.client.chat_postMessage(channel=ch_id, text=response, thread_ts=thread_ts)
            break
    return matched


""" ---------- PUBLICATION ANNOUNCEMENTS ---------- """

def reply_recent_papers(message):
    """Reply to a message with the most recent papers associated with a particular user

    Parameters
    ----------
    message : `Slack Message`
        A slack message object
    """
    orcids = []
    names = []
    direct_queries = True

    thread_ts = None if message["type"] == "message" else message["ts"]

    numbers = re.findall(r" \d* ", message["text"])
    n_papers = 1 if len(numbers) == 0 else int(numbers[0])

    # if don't find any then look for users instead
    if len(orcids) == 0:
        direct_queries = False
        # find any tags
        tags = re.findall(r"<[^>]*>", message["text"])

        # remove bot from the tags
        if f"<@{BOT_ID}>" in tags:
            tags.remove(f"<@{BOT_ID}>")

        # let people say "my" paper
        if len(tags) == 0 and message["text"].find("my") >= 0:
            tags.append(f"<@{message['user']}>")

        # if you found at least one tag
        if len(tags) > 0:
            # go through each of them
            for tag in tags:
                # convert the tag to an query and a name
                orcid, first_name, last_name = get_orcid_from_id(tag.replace("<@", "").replace(">", ""))
                print("ADS details:", orcid, first_name, last_name)

                # append info
                orcids.append(orcid)
                names.append(first_name + " " + last_name)

    # if we found no queries through all of that then crash out with a message
    if len(orcids) == 0:
        app.client.chat_postMessage(text=(f"{insert_british_consternation()} I think you asked for some "
                                          "recent papers but I couldn't find any ADS queries or user tags in "
                                          "the message sorry :pleading_face:"),
                                    channel=message["channel"], thread_ts=thread_ts)
        return

    # go through each orcid
    for i in range(len(orcids)):
        if orcids[i] is None:
            app.client.chat_postMessage(text=(f"{insert_british_consternation()} I'm terribly sorry old chap "
                                              "but I couldn't find an ORCID for this user :thinking-face:"),
                                        channel=message["channel"], thread_ts=thread_ts)
            continue

        # get the most recent n papers
        query = f'orcid:{orcids[i]}'
        papers = get_ads_papers(query=query)
        if papers is None:
            app.client.chat_postMessage(text=("Terribly sorry old chap but it seems that there's a problem "
                                              f"with that ADS query ({query}) :thinking-face:. Check you"
                                              "  don't have a typo of some sort!"),
                                        channel=message["channel"], thread_ts=thread_ts)
            return
        if len(papers) == 0:
            app.client.chat_postMessage(text=("Sorry but I couldn't find any papers for this query!"
                                              "If you think there should be"
                                              " some results then make sure you don't have a typo!"),
                                        channel=message["channel"], thread_ts=thread_ts)
            return

        # if it is just one paper then give lots of details
        if n_papers == 1:
            paper = papers[0]

            # create a brief message for before the paper
            preface = f"Here's the most recent paper for this query: {query}"
            authors = f"_Authors: {paper['authors']}_"

            # if you supplied tags (so we know their name)
            if not direct_queries:
                # use the tag in the pre-message
                preface = f"Here's the most recent paper from {tags[i]}"

                # create an author list, adding each but BOLDING the author that matches the grad
                authors = bold_uw_authors(paper['authors'])

            # format the date nicely
            date_formatted = custom_strftime("%B %Y", paper['date'])

            # send the pre-message then a big one with the paper info
            app.client.chat_postMessage(text=preface, channel=message["channel"], thread_ts=thread_ts)
            app.client.chat_postMessage(text=preface, blocks=[
                                            {
                                                "type": "section",
                                                "text": {
                                                    "type": "mrkdwn",
                                                    "text": f"*{sanitise_tags(paper['title'])}*"
                                                }
                                            },
                                            {
                                                "type": "section",
                                                "text": {
                                                    "type": "mrkdwn",
                                                    "text": authors
                                                }
                                            },
                                            {
                                                "type": "section",
                                                "fields": [
                                                    {
                                                        "type": "mrkdwn",
                                                        "text": f"_Date: {date_formatted}_"
                                                    },
                                                    {
                                                        "type": "mrkdwn",
                                                        "text": f"<{paper['link']}|ADS link>"
                                                    },
                                                    {
                                                        "type": "mrkdwn",
                                                        "text": f"Cited {paper['citations']} times so far"
                                                    }
                                                ]
                                            },
                                            {
                                                "type": "section",
                                                "text": {
                                                    "type": "mrkdwn",
                                                    "text": f"Abstract: {paper['abstract']}"
                                                }
                                            }
                                        ],
                                        channel=message["channel"], thread_ts=thread_ts)
        else:
            papers = papers[:n_papers]
            # if it's multiple papers then give a condensed list
            blocks = [
                [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (f"<{paper['link']}|*{sanitise_tags(paper['title'])}*> - "
                                     f"_{paper['authors'][0].split(' ')[0]} "
                                     f"et al. ({paper['date'].year})_ - Cited {paper['citations']} times")
                        }
                    }
                ] for paper in papers
            ]
            blocks = list(np.ravel(blocks))

            # same preface stuff as above but with many papers
            preface = (f"Here's the {n_papers} most recent papers for the query: {query}")

            # if you supplied tags (so we know their name)
            if not direct_queries:
                # use the tag in the pre-message
                preface = (f"Here's the {n_papers} most recent papers from {tags[i]}")

            # post the messages
            app.client.chat_postMessage(text=preface, channel=message["channel"], thread_ts=thread_ts)
            app.client.chat_postMessage(text=preface, blocks=blocks,
                                        channel=message["channel"], thread_ts=thread_ts, unfurl_links=False)


def get_orcid_from_id(user_id):
    """Convert a user ID to an orcid ID

    Parameters
    ----------
    user_id : `str`
        Slack ID of a user

    Returns
    -------
    query : `str`
        ADS Query

    name : `str`
        Person's full name
    """
    search_username = None

    id_table = pd.read_csv("data/user_ids.csv")
    matching_ids = id_table[id_table["id"] == user_id]
    if len(matching_ids) == 0:
        return None, None, None
    else:
        search_username = matching_ids["username"].values[0]

    # find matching orcid ID
    orcids = pd.read_csv("data/orcids.csv")
    matching_ids = orcids[orcids["username"] == search_username]
    if len(matching_ids) == 0:
        return None, None, None
    else:
        return matching_ids["orcid"].values[0], matching_ids["first_name"].values[0],\
            matching_ids["last_name"].values[0]



def any_new_publications():
    """ Check whether any new publications by grad students are out in the past week """
    no_new_papers = True

    initial_announcement = False

    # find the user ID of the person
    id_table = pd.read_csv("data/user_ids.csv")
    uw_authors = get_uw_authors()

    # go through the file of grads
    orcid_file = pd.read_csv("data/orcids.csv")
    for i, row in orcid_file.iterrows():
        query = f'orcid:{row["orcid"]}'

        # get the papers from the last week
        weekly_papers = get_ads_papers(query, past_week=True, remove_known_papers=True)

        # skip anyone who has a bad query
        if weekly_papers is None:
            continue

        # if this person has one then announce it!
        if len(weekly_papers) > 0:
            save_papers(weekly_papers)
            no_new_papers = False

            # if Geoffrey hasn't announced that he's looking at papers yet
            if not initial_announcement:
                # send an announcement and remember to not do that next time
                app.client.chat_postMessage(text=("It's time for our weekly paper round up, let's see "
                                                    "what everyone's been publishing in this last week!"),
                                            channel=find_channel(PAPERS_CHANNEL))
                initial_announcement = True

            for paper in weekly_papers:
                announce_publication(get_author_ids(id_table, paper["authors"], uw_authors), paper)

    if no_new_papers:
        print("No new papers!")


def get_author_ids(id_table, authors, uw_authors):
    author_ids = []

    # go through each author in the list
    for author in authors:
        split_author = list(reversed(author.split(", ")))

        # get their first initial and last name
        first_initial, last_name = split_author[0][0].lower(), split_author[-1].lower()

        # NOTE: I assume if first initial and last name match then it is the right person
        if last_name in uw_authors and first_initial in uw_authors[last_name]:
            id_table["first_initial"] = id_table["real_name"].apply(lambda x: x.split(" ")[0][0].lower())
            id_table["last_name"] = id_table["real_name"].apply(lambda x: x.split(" ")[-1].lower())
            
            # find row in the table that matches
            matched_id = id_table[(id_table["first_initial"] == first_initial) & (id_table["last_name"] == last_name)]
            if len(matched_id) > 0:
                author_ids.append(matched_id["id"].values[0])
    return author_ids


def announce_publication(user_ids, paper):
    """Announce to the workspace that someone has published a new paper(s)

    Parameters
    ----------
    user_id : `str`
        Slack user ID of the people who published the paper
    papers : `dict`
        Dictionaries of the paper
    """

    # choose an random adjective
    adjective = np.random.choice(["Splendid", "Tremendous", "Brilliant",
                                  "Excellent", "Fantastic", "Spectacular"])
    
    user_id_strings = [f"<@{user_id}>" for user_id in user_ids]
    # join user ids with commas and an "and" at the end
    if len(user_id_strings) == 1:
        author_id_string = user_id_strings[0]
    else:
        author_id_string = ", ".join(user_id_strings[:-1]) + " and " + user_id_strings[-1]

    preface = f"Look what I found! :tada: {adjective} work from {author_id_string} :clap:"
    outro = ("I put the abstract in the thread for anyone interested in learning more "
                f"- again, a big congratulations to {author_id_string} for this awesome paper")

    # add the same starting blocks for all
    start_blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text":f"{sanitise_tags(paper['title'])}",
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": preface
            }
        },
    ]

    # add some blocks for each paper
    paper_blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": bold_uw_authors(paper["authors"])
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<{paper['link']}|*ADS Link*>"
            }
        }
    ]

    # add a single end block about the abstract
    end_blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": outro
            }
        }
    ]

    # combine all of the blocks
    blocks = start_blocks + paper_blocks + end_blocks

    # create blocks for each abstract
    abstract_blocks = [
        [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": p['abstract']
                }
            }
        ] for p in [paper]
    ]

    # flatten out the blocks into the right format
    blocks = list(np.ravel(blocks))
    abstract_blocks = list(np.ravel(abstract_blocks))

    # find the channel and send the initial message
    channel = find_channel(PAPERS_CHANNEL)
    message = app.client.chat_postMessage(text="Congrats on your new paper!",
                                          blocks=blocks, channel=channel, unfurl_links=False)

    # reply in thread with the abstracts
    app.client.chat_postMessage(text="Your paper abstract:", blocks=abstract_blocks,
                                channel=channel, thread_ts=message["ts"])


""" ---------- HELPER FUNCTIONS ---------- """

def save_all_user_ids():
    """Save all user IDs to a file for future reference"""
    users = app.client.users_list()["members"]

    real_names, usernames, ids = [], [], []
    for user in users:
        if "real_name" in user and "name" in user and "id" in user:
            real_names.append(user["real_name"])
            usernames.append(user["name"])
            ids.append(user["id"])

    df = pd.DataFrame({"username": usernames, "id": ids, "real_name": real_names})
    df.to_csv("data/user_ids.csv", index=False)


def insert_british_consternation():
    choices = ["Oh fiddlesticks!", "Ah burnt crumpets!", "Oops, I've bangers and mashed it!",
               "It seems I've had a mare!", "It appears I've had a mare!",
               "Everything is very much not tickety-boo!", "Oh dearie me!",
               "My profuse apologies but we've got a problem!",
               "I haven't the foggiest idea what just happened!",
               ("Oh dear, one of my servers just imploded so that can't be a terribly positive "
                "sign :exploding_head:"),
               "Ouch! Did you know errors hurt me? :smiling_face_with_tear:"]
    return np.random.choice(choices)


def find_channel(channel_name):
    """Find the ID of a slack channel

    Parameters
    ----------
    channel_name : `str`
        Name of the Slack channel

    Returns
    -------
    ch_id : `str`
        ID of the Slack channel
    """
    # grab the list of channels
    channels = app.client.conversations_list(exclude_archived=True, limit=500)
    ch_id = None

    # go through each and find one with the same name
    for channel in channels["channels"]:
        if channel["name"] == channel_name:
            # save the ID and break
            ch_id = channel["id"]
            break

    # if you didn't find one then send out a warning (who changed the channel name!?)
    if ch_id is None:
        print(f"WARNING: couldn't find channel '{channel_name}'")
    return ch_id


def suffix(d):
    """ Work out what suffix a date needs """
    return 'th' if 11 <= d <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 10, 'th')


def custom_strftime(format, t):
    """ Change the default datetime strftime to use the custom suffix """
    return t.strftime(format).replace('{S}', str(t.day) + suffix(t.day))

def sanitise_tags(str):
    # The regular expression pattern for substrings between < and >
    pattern = "<.*?>"
    # Use re.sub() to replace the matched substrings with an empty string
    output_string = re.sub(pattern, "", str)
    return output_string


def every_morning():
    """ This function runs every morning around 9AM """
    save_all_user_ids()
    today = datetime.datetime.now()
    the_day = today.strftime("%A")

    if the_day == "Wednesday":
        any_new_publications()


# start Geoffrey
if __name__ == "__main__":
    scheduler = BackgroundScheduler({'apscheduler.timezone': 'US/Pacific'})
    scheduler.add_job(every_morning, "cron", hour=9, minute=32)
    scheduler.start()
    SocketModeHandler(app, os.environ["GEOFFREY_APP_TOKEN"]).start()


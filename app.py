import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import re
import requests

import numpy as np
import datetime
import pandas as pd

from apscheduler.schedulers.background import BackgroundScheduler

from ads_query import bold_uw_authors, get_ads_papers, save_papers, get_uw_authors, check_uw_authors

# Initializes your app with your bot token and socket mode handler
app = App(token=os.environ.get("GEOFFREY_BOT_TOKEN"))
BOT_ID = "U06V23JH71R"
PAPERS_CHANNEL = "geoffrey-testing"

""" ---------- APP HOME ---------- """
@app.event("app_home_opened")
def update_home_tab(client, event, logger):
    try:
        home_blocks = {
            "type": "home",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": ":house: Salutations my friend and welcome to my humble abode!",
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "My name's Geoffrey. I like reading papers. Help me read yours!"
                    }
                },
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": ":bust_in_silhouette: Your information",
                    }
                },
            ]
        }

        orcids = pd.read_csv("data/orcids.csv")
        matching_rows = orcids[orcids["slack_id"] == event["user"]]
        if len(matching_rows) == 0:
            no_info_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Sorry <@" + event["user"] + ">, it seems we haven't met yet! :wave: Would you be a dear and tell me a bit about yourself for me?"
                }
            }
            home_blocks["blocks"].append(no_info_block)
        else:
            info = matching_rows.iloc[0]
            info_blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Lovely to see you again <@" + event["user"] + ">! :relaxed: If my memory serves me, your information is:"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f":abc: *First name*: {info['first_name']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f":tulip: *ORCID*: {info['orcid']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f":abc: *Last name*: {info['last_name']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f":scientist: *Role*: {info['role']}"
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Let me know if I should update any of this with the button below."
                    }
                }
            ]
            home_blocks["blocks"] += info_blocks

        home_blocks["blocks"] += [
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Update info",
                        },
                        "value": f"{event['user']}" if len(matching_rows) == 0 else f"{event['user']},{info['first_name']},{info['last_name']},{info['orcid']},{info['role']}",
                        "action_id": "update-user-info-open"
                    }
                ]
            },
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": ":open_file_folder: Full paper list",
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "If you'd like to get a CSV file of all the papers I've got in my databanks then click the button below!"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Get full paper file",
                        },
                        "value": f"{event['user']}",
                        "action_id": "send-all-papers"
                    }
                ]
            }
        ]

        # Call views.publish with the built-in client
        client.views_publish(user_id=event["user"], view=home_blocks)
    except Exception as e:
        logger.error(f"Error publishing home tab: {e}")


@app.action("update-user-info-open")
def update_user_info_open(ack, body, client):
    ack()

    # open the modal when someone clicks the button
    user_and_info = body["actions"][0]["value"]
    if "," in user_and_info:
        user, first_name, last_name, orcid, role = user_and_info.split(",")
    else:
        user = user_and_info
        first_name, last_name, orcid, role = "", "", "", ""

    possible_roles = ["Undergraduate", "Graduate Student", "Postdoc", "Research Scientist", "Acting Instructor",
                      "Teaching Faculty", 'Research Assistant Professor', 'Research Associate Professor',
                      'Assistant Professor', 'Associate Professor', 'Professor', 'Professor Emeritus']

    select_block = {
        "type": "input",
        "block_id": "role",
        "element": {
            "type": "static_select",
            "placeholder": {
                "type": "plain_text",
                "text": "Select your role",
            },
            "options": [
                {
                    "text": {
                        "type": "plain_text",
                        "text": r,
                    },
                    "value": r
                } for r in possible_roles
            ],
        },
        "label": {
            "type": "plain_text",
            "text": "Role",
            "emoji": True
        }
    }

    if role != "":
        select_block["element"]["initial_option"] = {
            "text": {
                "type": "plain_text",
                "text": role,
            },
            "value": role
        }

    client.views_open(trigger_id=body["trigger_id"], view={
        "callback_id": "update-user-info",
        "title": {
            "type": "plain_text",
            "text": "Introductions",
            "emoji": True
        },
        "submit": {
            "type": "plain_text",
            "text": "Submit",
            "emoji": True,
        },
        "type": "modal",
        "close": {
            "type": "plain_text",
            "text": "Cancel",
            "emoji": True
        },
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Tell me about yourself!",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Let's make sure I have all the right info about you <@{user}>, please fill out the form below :relaxed:"
                }
            },
            {
                "type": "input",
                "block_id": "first-name",
                "element": {
                    "type": "plain_text_input",
                    "initial_value": first_name,
                },
                "label": {
                    "type": "plain_text",
                    "text": "First name",
                    "emoji": True
                }
            },
            {
                "type": "input",
                "block_id": "last-name",
                "element": {
                    "type": "plain_text_input",
                    "initial_value": last_name,
                },
                "label": {
                    "type": "plain_text",
                    "text": "Last name",
                    "emoji": True
                }
            },
            select_block,
            {
                "type": "input",
                "block_id": "orcid",
                "element": {
                    "type": "plain_text_input",
                    "initial_value": orcid,
                },
                "label": {
                    "type": "plain_text",
                    "text": "ORCID",
                }
            },
        ]
    })

def orcid_checksum(orcid):
    """Check whether an ORCID is valid

    Based on the checksum algorithm described here:
    https://support.orcid.org/hc/en-us/articles/360006897674-Structure-of-the-ORCID-Identifier

    Parameters
    ----------
    orcid : `str`
        Full ORCID

    Returns
    -------
    valid : `bool`
        Whether the ORCID is valid
    """
    total = 0
    for char in orcid[:-1]:
        if char == "-":
            continue
        digit = int(char)
        total = (total + digit) * 2
    remainder = total % 11
    result = (12 - remainder) % 11
    check_digit = "X" if result == 10 else str(result)
    return check_digit == orcid[-1]

@app.view("update-user-info")
def update_user_info(ack, body, client):
    ack()

    user = body["user"]["id"]
    state = body["view"]["state"]["values"]

    first_name = list(state['first-name'].values())[0]['value']
    last_name = list(state['last-name'].values())[0]['value']
    role = list(state['role'].values())[0]['selected_option']['value']
    orcid = list(state['orcid'].values())[0]['value']

    # ensure that the ORCID is four groups of four digits separated by hyphens
    if not (re.match(r"\d{4}-\d{4}-\d{4}-[\dX]{4}", orcid)
            and len(orcid) == 4*4 + 3
            and orcid_checksum(orcid)):
        client.chat_postMessage(channel=user,
                                text=(f"So...I have good news and bad news <@{user}>.\n\n:this-is-fine-fire: The bad news is that "
                                      "the ORCID you just submitted doesn't look quite right. It should be "
                                      "four groups of four digits separated by hyphens, but you submitted "
                                      f"``{orcid}``.\n\n:woohoo: The good news is that I won't hold it against you because "
                                      "I know typing numbers can be hard with your little human fingers "
                                      ":upside_down_face: Give it another go and I'm sure you'll get it "
                                      "right, I believe in you!"))
    else:
        orcids = pd.read_csv("data/orcids.csv")
        matching_rows = orcids[orcids["slack_id"] == user]
        if len(matching_rows) == 0:
            orcids.loc[len(orcids)] = [orcid, first_name, last_name, role, user]
        else:
            orcids.loc[matching_rows.index, "first_name"] = first_name
            orcids.loc[matching_rows.index, "last_name"] = last_name
            orcids.loc[matching_rows.index, "role"] = role
            orcids.loc[matching_rows.index, "orcid"] = orcid

        orcids.to_csv("data/orcids.csv", index=False)

        client.chat_postMessage(channel=user, text=(f"Thanks for updating your information <@{user}>, "
                                                    "looking forward to reading your papers! :relaxed:"))
        update_home_tab(client, {"user": user}, None)
        

@app.action("send-all-papers")
def send_all_papers(ack, body, client):
    ack()

    # get the user ID from the action
    user = body["actions"][0]["value"]

    # get the direct message channel ID for this user
    user_dm = client.conversations_open(users=user)["channel"]["id"]

    # calculate the file size and get the upload URL
    file_stats = os.stat("data/papers.csv")
    upload_res = client.files_getUploadURLExternal(filename="papers.csv", length=file_stats.st_size)
    
    # if the upload was successful then send the file
    if upload_res["ok"]:
        
        # perform a POST request using requests to the upload URL as raw bytes
        with open("data/papers.csv", "rb") as f:
            r = requests.post(upload_res["upload_url"], files={'upload_file': open('data/papers.csv','rb')})
            if r.status_code == 200:
                # complete the request with a message to the user
                client.files_completeUploadExternal(channel_id=user_dm,
                                                    initial_comment="Here's the file you wanted!",
                                                    files=[{'id': upload_res['file_id'], "title": "papers.csv"}])
            else:
                # if the upload failed then send a message to the user
                client.chat_postMessage(channel=user_dm, text=f"{insert_british_consternation()} Sorry, I couldn't get the file to upload to Slack for you, I'm not sure what went wrong :pleading_face: Maybe try again?")
    else:
        # if we couldn't get the upload URL then send a message to the user
        client.chat_postMessage(channel=user_dm, text=f"{insert_british_consternation()} Sorry, I couldn't get the file for you, I'm not sure what went wrong :pleading_face: Maybe try again?")


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
    direct_queries = True

    thread_ts = None if message["type"] == "message" else message["ts"]

    numbers = re.findall(r"\d+", message["text"])
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
                orcid = get_orcid_from_id(tag.replace("<@", "").replace(">", ""))

                # append info
                orcids.append(orcid)

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
            app.client.chat_postMessage(text=(f"I'm terribly sorry old chap but I couldn't find an ORCID for "
                                              "this user :sweat_smile: You should get them to introduce "
                                              "themself to me in my home page, I always enjoy making a new "
                                              "friend!"),
                                        channel=message["channel"], thread_ts=thread_ts)
            continue

        # get the most recent n papers
        query = f'orcid:{orcids[i]}'
        papers = get_ads_papers(query=query)
        if papers is None:
            app.client.chat_postMessage(text=("Terribly sorry old chap but it seems that there's a problem "
                                              f"with that ADS query ({query}) :sweat_smile:. Check you"
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
    orcids = pd.read_csv("data/orcids.csv")
    matching_rows = orcids[orcids["slack_id"] == user_id]
    if len(matching_rows) == 0:
        return None
    else:
        return matching_rows["orcid"].values[0]



def any_new_publications():
    """ Check whether any new publications came out in the past week """
    print("Starting paper search!")
    no_new_papers = True

    initial_announcement = False

    # find the user ID of all UW authors
    uw_authors = get_uw_authors()

    # go through the file of people in the department
    orcid_file = pd.read_csv("data/orcids.csv")
    papers = []
    no_new_papers = False

    for i, row in orcid_file.iterrows():
        break
        query = f'orcid:{row["orcid"]}'

        # get the papers from the last week
        weekly_papers = get_ads_papers(query, past_week=True, remove_known_papers=True)

        # skip anyone who has a bad query
        if weekly_papers is None:
            continue

        # if this person has one then announce it!
        if len(weekly_papers) > 0:
            papers += weekly_papers
            no_new_papers = False
            continue
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
                announce_publication(get_author_ids(orcid_file, paper["authors"], uw_authors), paper)

    if no_new_papers:
        print("No new papers!")
        return

    print("All done with the paper search!")
    print(papers)
    
    papers = [{'link': 'https://ui.adsabs.harvard.edu/abs/2025ApJ...978...76Z/abstract', 'title': 'Microlensing Events in Five Years of Photometry from the Zwicky Transient Facility', 'abstract': 'Microlensing has a unique advantage for detecting dark objects in the Milky Way, such as free-floating planets, neutron stars, and stellar-mass black holes. Most microlensing surveys focus on the Galactic bulge, where higher stellar density leads to a higher event rate. However, microlensing events in the Galactic plane have closer lenses and longer timescales, which leads to a greater chance of measuring microlens parallax, providing an additional constraint on the mass of the lens. This work searches for microlensing events in Zwicky Transient Facility (ZTF) Data Release 17 from 2018 to 2023 in the Galactic plane region. We find 124 high-confidence microlensing events and 54 possible events, all available online (see footnote 11). Thus, with 2 yr of additional ZTF data in DR17, we have more than doubled the number of microlensing events (60) found in the previous 3 yr DR5 search. In the event selection, we use the efficient EventFinder algorithm to detect microlensing signals, which could be used for large data sets such as future ZTF data releases or data from the Rubin Observatory Legacy Survey of Space and Time. Using detection efficiencies of ZTF fields obtained from catalog-level simulations, we calculate the mean Einstein timescale to be &lt;t <SUB>E</SUB>&gt; = 51.7 ± 3.3 days, smaller than previous results of the Galactic plane but within 1.5σ. We also calculate optical depths and event rates, although some caution is needed due to the use of visual inspection when creating our final sample. Spectroscopy of three possible candidates confirms their microlensing nature.', 'authors': ['Zhai, Ruocheng', 'Rodriguez, Antonio C.', 'Mao, Shude', 'Lam, Casey Y.', 'Bellm, Eric C.', 'Purdum, Josiah', 'Masci, Frank J.', 'Wold, Avery'], 'date': datetime.date(2025, 1, 1), 'citations': 2, 'reads': 162, 'keywords': ['Milky Way disk', 'Gravitational microlensing', '1050', '672', 'Astrophysics - Astrophysics of Galaxies', 'Astrophysics - Instrumentation and Methods for Astrophysics', 'Astrophysics - Solar and Stellar Astrophysics'], 'publisher': 'The Astrophysical Journal'},
    {'link': 'https://ui.adsabs.harvard.edu/abs/2024ApJ...977..262C/abstract', 'title': 'Expanding the Ultracompacts: Gravitational-wave-driven Mass Transfer in the Shortest-period Binaries with Accretion Disks', 'abstract': 'We report the discovery of three ultracompact binary white dwarf systems hosting accretion disks, with orbital periods of 7.95, 8.68, and 13.15 minutes. This significantly augments the population of mass-transferring binaries at the shortest periods, and provides the first evidence that accretors in ultracompacts can be dense enough to host accretion disks even below 10 minutes (where previously only direct-impact accretors were known). In the two shortest-period systems, we measured changes in the orbital periods driven by the combined effect of gravitational-wave emission and mass transfer. We find <inline-formula> </inline-formula> is negative in one case, and positive in the other. This is only the second system measured with a positive <inline-formula> </inline-formula>, and it is the most compact binary known that has survived a period minimum. Using these systems as examples, we show how the measurement of <inline-formula> </inline-formula> is a powerful tool in constraining the physical properties of binaries, e.g., the mass and mass–radius relation of the donor stars. We find that the chirp masses of ultracompact binaries at these periods seem to cluster around <inline-formula> </inline-formula>, perhaps suggesting a common origin for these systems or a selection bias in electromagnetic discoveries. Our new systems are among the highest-amplitude known gravitational-wave sources in the millihertz regime, providing an exquisite opportunity for multimessenger study with future space-based observatories such as LISA and TianQin. We discuss how such systems provide fascinating laboratories to study the unique regime where the accretion process is mediated by gravitational waves.', 'authors': ['Chakraborty, Joheen', 'Burdge, Kevin B.', 'Rappaport, Saul A.', 'Munday, James', 'Chen, Hai-Liang', 'Rodríguez-Gil, Pablo', 'Dhillon, V. S.', 'Hughes, Scott A.', 'Nelemans, Gijs', 'Kara, Erin', 'Bellm, Eric C.', 'Brown, Alex J.', 'Castro Segura, Noel', 'Chen, Tracy X.', 'Chickles, Emma', 'Dyer, Martin J.', 'Dekany, Richard', 'Drake, Andrew J.', 'Garbutt, James', 'Graham, Matthew J.', 'Green, Matthew J.', 'Jarvis, Dan', 'Kennedy, Mark R.', 'Kerry, Paul', 'Kulkarni, S. R.', 'Littlefair, Stuart P.', 'Mahabal, Ashish A.', 'Masci, Frank J.', 'McCormac, James', 'Parsons, Steven G.', 'Pelisoli, Ingrid', 'Pike, Eleanor', 'Prince, Thomas A.', 'Riddle, Reed', 'van Roestel, Jan', 'Sahman, Dave', 'Wold, Avery', 'Sunny Wong, Tin Long'], 'date': datetime.date(2024, 12, 1), 'citations': 2, 'reads': 580, 'keywords': ['Compact binary stars', 'Gravitational wave sources', 'Stellar accretion disks', 'White dwarf stars', '283', '677', '1579', '1799', 'Astrophysics - High Energy Astrophysical Phenomena', 'Astrophysics - Solar and Stellar Astrophysics'], 'publisher': 'The Astrophysical Journal'},
    {'link': 'https://ui.adsabs.harvard.edu/abs/2025ApJS..276....8G/abstract', 'title': 'The Local Ultraviolet to Infrared Treasury. I. Survey Overview of the Broadband Imaging', 'abstract': 'The Local Ultraviolet to Infrared Treasury (LUVIT) is a Hubble Space Telescope program that combines newly acquired data in the near-ultraviolet (NUV), optical, and near-infrared (NIR) with archival optical and NIR imaging to produce multiband panchromatic resolved stellar catalogs for 23 pointings in 22 low-mass, star-forming galaxies ranging in distance from the outskirts of the Local Group to ∼3.8 Mpc. We describe the survey design, detail the LUVIT broadband filter observations and the archival data sets included in the LUVIT reductions, and summarize the simultaneous multiband data reduction steps. The spatial distributions and color–magnitude diagrams (CMDs) from the resulting stellar catalogs are presented for each target, from the NUV to the NIR. We demonstrate in which regions of the CMDs stars with NUV and optical, optical and NIR, and NUV through NIR detections reside. For each target, we use the results from artificial star tests to measure representative completeness, bias, and total photometric uncertainty as a function of magnitude in each broadband filter. We also assess which LUVIT targets have significant spatial variation in the fraction of stars recovered at a given magnitude. The panchromatic LUVIT stellar catalogs will provide a rich legacy data set for a host of resolved stellar population studies.', 'authors': ['Gilbert, Karoline M.', 'Choi, Yumi', 'Boyer, Martha L.', 'Williams, Benjamin F.', 'Weisz, Daniel R.', 'Bell, Eric F.', 'Dalcanton, Julianne J.', 'McQuinn, Kristen B. W.', 'Skillman, Evan D.', 'Costa, Guglielmo', 'Dolphin, Andrew E.', 'Fouesneau, Morgan', 'Girardi, Léo', 'Goldman, Steven R.', 'Gordon, Karl D.', 'Guhathakurta, Puragra', 'Gull, Maude', 'Hagen, Lea', 'Huynh, Ky', 'Lindberg, Christina W.', 'Marigo, Paola', 'Murray, Claire E.', 'Pastorelli, Giada', 'Yanchulova Merica-Jones, Petia'], 'date': datetime.date(2025, 1, 1), 'citations': 0, 'reads': 275, 'keywords': ['Stellar populations', 'Dwarf irregular galaxies', 'Multi-color photometry', '1622', '417', '1077', 'Astrophysics - Astrophysics of Galaxies'], 'publisher': 'The Astrophysical Journal Supplement Series'},
    {'link': 'https://ui.adsabs.harvard.edu/abs/2024ApJ...977..179G/abstract', 'title': 'Exploring the Diversity of Faint Satellites in the M81 Group', 'abstract': "In the last decade, we have been able to probe further down the galaxy luminosity function than ever before and expand into the regime of ultra-faint dwarfs (UFDs), which are some of the best probes we have of small-scale cosmology and galaxy formation. Digital sky surveys have enabled the discovery and study of these incredibly low-mass, highly dark-matter-dominated systems around the Local Group, but it is critical that we expand the satellite census further out to understand if Milky Way and M31 satellites are representative of dwarf populations in the local Universe. Using data from the Hubble Space Telescope (HST) Advanced Camera for Surveys (ACS), we present updated characterization of four satellite systems in the M81 group. These systems—D1005+68, D1006+69, DWJ0954+6821, and D1009+68—were previously discovered using ground-based Subaru Hyper Suprime-Cam data as overdensities in M81's halo, and are now confirmed with HST/ACS by this work. These are all faint (M <SUB> V </SUB> ≥ ‑7.9) and consistent with old (∼13 Gyr), metal-poor ([M/H] &lt; ‑1.5) populations. Each system possesses relatively unusual features—including one of the most concentrated satellite galaxies with a Sérsic index of n ∼ 5, one of the most elliptical galaxies outside the Local Group with an ϵ ∼ 0.6, and one of the most compact galaxies for its magnitude. Two of the satellites have very low surface brightness, lower than most known galaxies in this absolute magnitude range. This work previews the scientific promise of the upcoming Rubin Observatory and Roman Telescope for illuminating the diversity of UFDs in the Local Volume and beyond.", 'authors': ['Gozman, Katya', 'Bell, Eric F.', 'Jang, In Sung', 'Arias, Jose Marco', 'Bailin, Jeremy', 'de Jong, Roelof S.', "D'Souza, Richard", 'Gnedin, Oleg Y.', 'Monachesi, Antonela', 'Price, Paul A.', 'Rao, Vaishnav V.', 'Smercina, Adam'], 'date': datetime.date(2024, 12, 1), 'citations': 0, 'reads': 398, 'keywords': ['Dwarf galaxies', 'Low surface brightness galaxies', 'Galaxies', 'HST photometry', 'Hubble Space Telescope', 'RGB photometry', '416', '940', '573', '756', '761', '1397', 'Astrophysics - Astrophysics of Galaxies'], 'publisher': 'The Astrophysical Journal'},
    {'link': 'https://ui.adsabs.harvard.edu/abs/2024RNAAS...8..303N/abstract', 'title': 'Mock JWST Colors of Two Different Star Formation Histories at z ~ 4', 'abstract': 'In this work, we test if JWST NIRCam filters can distinguish between two different galaxy star formation histories (SFHs) at z = 3–4. We use the Code Investigating GALaxy Emission to model F150W, F277W, and F770W-band magnitudes for mock massive galaxies at 3.5 &lt; z &lt; 4.5 generating two different SFHs: (1) a delayed-τ, analogous to a starburst-like galaxy with a mostly uniform stellar population, and (2) a decayed exponential with a late burst to represent a more even mixture of old and young stellar populations. We explored the F277W ‑ F770W versus F150W ‑ F277W color space, and determined that the delayed-τ SFH produces highly clustered, relatively "flat" colors in both planes; whereas the other SFH produces more diversity across this color space. This work motivates further studies on the potential for JWST colors to rapidly identify varying evolutionary pathways for galaxies at z = 3–4.', 'authors': ['Nere, Rachel', 'Long, Arianna S.'], 'date': datetime.date(2024, 12, 1), 'citations': 0, 'reads': 0, 'keywords': ['Galaxy colors', 'Two-color diagrams', 'Starburst galaxies', '586', '1724', '1570'], 'publisher': 'Research Notes of the American Astronomical Society'},
    {'link': 'https://www.tomwagg.com', 'title': "Invented test paper", 'abstract': 'This is a test paper that I made up for testing purposes', 'authors': ['Wagg, Tom'], 'date': datetime.date(2024, 12, 1), 'citations': 0, 'reads': 0, 'keywords': ['Test paper'], 'publisher': 'Tom Wagg'}
    ]


    start_blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":telescope: Geoffrey's Weekly Paper Roundup ({datetime.date.today()})"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": np.random.choice([
                    "Wow what a week huh :sweat_smile: Let's take some time away from our toils to appreciate the hard work of our colleagues!",
                    "Not to fear, Geoffrey is here! I've got exactly what you need to satisfy the yearning in your soul - new papers! :rolled_up_newspaper:",
                    "Goodness what a delightful time I've had perusing ADS this week - check out these tremendous papers! :tada:",
                    "What better way to start the day than to see your colleagues' fascinating new work? :sunrise:",
                    "Oh my, we've got a real treat for you today - some splendid new papers from our colleagues! :tada:",
                    "What have we here? Perchance an opportunity for someone to tell us more about this in a Roundup talk (hint hint)? :eyes:",
                ])
            }
        },
    ]

    first_author_blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*First Author Papers*"
            }
        },
		{
			"type": "divider"
		},
    ]

    co_author_blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Co-Author Papers*"
            }
        },
		{
			"type": "divider"
		},
    ]

    thread_msgs = []

    for paper in papers:
        user_id_strings = [f"<@{user_id}>" for user_id in get_author_ids(orcid_file, paper["authors"], uw_authors)]
        # join user ids with commas and an "and" at the end
        if len(user_id_strings) == 1:
            author_id_string = user_id_strings[0]
        else:
            author_id_string = ", ".join(user_id_strings[:-1]) + " and " + user_id_strings[-1]

        new_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (f"<{paper['link']}|*{sanitise_tags(paper['title'])}*>" + "\n"
                            f"\t_{paper['authors'][0].split(' ')[0]} "
                            f"et al. ({paper['date'].year})_ - including UW authors {author_id_string}")
            }
        }
        if check_uw_authors(paper, uw_authors)[0]:
            first_author_blocks.append(new_block)
        else:
            co_author_blocks.append(new_block)


        # shorten long titles
        title = sanitise_tags(paper["title"])
        if len(title) > 150:
            title = title[:147] + "..."

        # add the same starting blocks for all
        title_block = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text":f"{title}",
                }
            },
        ]
        content_block = [
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

        # create blocks for each abstract
        abstract_block = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": paper['abstract']
                }
            }
        ]

        # combine all of the blocks
        thread_msgs.append(title_block + content_block + abstract_block)

    blocks = start_blocks + first_author_blocks + co_author_blocks

    channel = find_channel(PAPERS_CHANNEL)
    message = app.client.chat_postMessage(text="Congrats on your new paper!",
                                          blocks=blocks, channel=channel, unfurl_links=False)
    
    # reply in thread with the abstracts
    for abstract_blocks in thread_msgs:
        app.client.chat_postMessage(text="Your paper details:", blocks=abstract_blocks,
                                    channel=channel, thread_ts=message["ts"], unfurl_links=False)


def get_author_ids(orcids, authors, uw_authors):
    author_ids = []
    orcids["first_initial"] = orcids["first_name"].apply(lambda x: x[0].lower())
    orcids["last_name_lower"] = orcids["last_name"].apply(lambda x: x.lower())

    # go through each author in the list
    for author in authors:
        split_author = list(reversed(author.split(", ")))

        # get their first initial and last name
        first_name, last_name = split_author[0].split(" ")[0].lower(), split_author[-1].lower()
        first_initial = first_name[0]

        # NOTE: It matches either on the full first name or just first initial if the first name is just an initial
        if last_name in uw_authors:
            if len(first_name) == 2 and first_name[1] == '.':
                first_name = first_name[0]
            found_one = False
            for option in uw_authors[last_name]:
                if (len(option) > 1 and option == first_name[:len(option)]) or option == first_name:
                    found_one = True

            if not found_one:
                continue

            # find row in the table that matches
            matched_id = orcids[(orcids["first_initial"] == first_initial) & (orcids["last_name_lower"] == last_name)]
            if len(matched_id) > 0:
                author_ids.append(matched_id["slack_id"].values[0])
    return author_ids


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


import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db, get_session, Builder

X_BUILDERS = [
    {"name": "Andrej Karpathy",   "handle": "karpathy",      "category": "lab"},
    {"name": "Swyx",              "handle": "swyx",           "category": "observer"},
    {"name": "Josh Woodward",     "handle": "joshwoodward",   "category": "lab"},
    {"name": "Kevin Weil",        "handle": "kevinweil",      "category": "lab"},
    {"name": "Peter Yang",        "handle": "petergyang",     "category": "observer"},
    {"name": "Nan Yu",            "handle": "thenanyu",       "category": "builder"},
    {"name": "Madhu Guru",        "handle": "realmadhuguru",  "category": "builder"},
    {"name": "Amanda Askell",     "handle": "AmandaAskell",   "category": "lab"},
    {"name": "Cat Wu",            "handle": "_catwu",         "category": "builder"},
    {"name": "Thariq",            "handle": "trq212",         "category": "builder"},
    {"name": "Google Labs",       "handle": "GoogleLabs",     "category": "lab"},
    {"name": "Amjad Masad",       "handle": "amasad",         "category": "founder"},
    {"name": "Guillermo Rauch",   "handle": "rauchg",         "category": "founder"},
    {"name": "Alex Albert",       "handle": "alexalbert__",   "category": "lab"},
    {"name": "Aaron Levie",       "handle": "levie",          "category": "founder"},
    {"name": "Ryo Lu",            "handle": "ryolu_",         "category": "builder"},
    {"name": "Garry Tan",         "handle": "garrytan",       "category": "founder"},
    {"name": "Matt Turck",        "handle": "mattturck",      "category": "observer"},
    {"name": "Zara Zhang",        "handle": "zarazhangrui",   "category": "observer"},
    {"name": "Nikunj Kothari",    "handle": "nikunj",         "category": "builder"},
    {"name": "Peter Steinberger", "handle": "steipete",       "category": "builder"},
    {"name": "Dan Shipper",       "handle": "danshipper",     "category": "observer"},
    {"name": "Aditya Agarwal",    "handle": "adityaag",       "category": "observer"},
    {"name": "Sam Altman",        "handle": "sama",           "category": "lab"},
    {"name": "Claude",            "handle": "claudeai",       "category": "lab"},
]

PODCAST_BUILDERS = [
    {"name": "Latent Space",                   "rss_url": "https://api.substack.com/feed/podcast/1084089.rss"},
    {"name": "Training Data",                  "rss_url": "https://feeds.megaphone.fm/trainingdata"},
    {"name": "No Priors",                      "rss_url": "https://feeds.megaphone.fm/nopriors"},
    {"name": "Unsupervised Learning",          "rss_url": "https://feeds.simplecast.com/dOSE_bdP"},
    {"name": "The MAD Podcast with Matt Turck","rss_url": "https://anchor.fm/s/f2ee4948/podcast/rss"},
    {"name": "AI & I by Every",                "rss_url": "https://anchor.fm/s/ed1f5584/podcast/rss"},
]

BLOG_BUILDERS = [
    {"name": "Anthropic Engineering", "rss_url": "https://www.anthropic.com/engineering"},
    {"name": "Claude Blog",           "rss_url": "https://claude.com/blog"},
]


def seed():
    init_db()
    inserted = 0
    skipped = 0

    with get_session() as session:
        # X accounts — unique key: handle
        for b in X_BUILDERS:
            exists = session.query(Builder).filter_by(handle=b["handle"]).first()
            if exists:
                skipped += 1
                continue
            session.add(Builder(
                name=b["name"],
                handle=b["handle"],
                category=b["category"],
                is_default=1,
                is_active=1,
            ))
            inserted += 1

        # Podcasts — unique key: name (handle is NULL)
        for b in PODCAST_BUILDERS:
            exists = session.query(Builder).filter_by(name=b["name"], category="podcast").first()
            if exists:
                skipped += 1
                continue
            session.add(Builder(
                name=b["name"],
                handle=None,
                rss_url=b["rss_url"],
                category="podcast",
                is_default=1,
                is_active=1,
            ))
            inserted += 1

        # Blogs — unique key: name (handle is NULL)
        for b in BLOG_BUILDERS:
            exists = session.query(Builder).filter_by(name=b["name"], category="blog").first()
            if exists:
                skipped += 1
                continue
            session.add(Builder(
                name=b["name"],
                handle=None,
                rss_url=b["rss_url"],
                category="blog",
                is_default=1,
                is_active=1,
            ))
            inserted += 1

    print(f"Seed complete: {inserted} inserted, {skipped} skipped.")


if __name__ == "__main__":
    seed()

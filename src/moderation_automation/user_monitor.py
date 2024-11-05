import logging
import sqlite3
from argparse import ArgumentParser as ArgParser

import praw

LOGGER = logging.getLogger(__file__)


class RedditMonitor:
    def __init__(self, subreddit):
        # Reddit stuff
        self._reddit = praw.Reddit()
        self.username = self._reddit.user.me().name
        LOGGER.debug("Reddit login ok")
        self.subreddit = subreddit
        self._conn = self.init_db()
        self._sub = self._reddit.subreddit(subreddit)

    def init_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"{self.subreddit}.db")
        conn.executescript(
            """CREATE TABLE IF NOT EXISTS banned (
            id VARCHAR(50) NOT NULL,
            username VARCHAR(20) NOT NULL,
            duration VARCHAR(10),
            created_utc INTEGER,
            PRIMARY KEY (id)
            );
            CREATE INDEX IF NOT EXISTS idx_banned_username ON banned (username);
            CREATE INDEX IF NOT EXISTS idx_banned_created_utc ON banned (created_utc);
        """
        )
        conn.executescript(
            """CREATE TABLE IF NOT EXISTS mod_removed (
            id VARCHAR(50) NOT NULL,
            username VARCHAR(20) NOT NULL,
            target VARCHAR(10),
            post VARCHAR(10),
            created_utc INTEGER,
            PRIMARY KEY (id)
            );
            CREATE INDEX IF NOT EXISTS idx_mod_removed_username ON mod_removed (username);
            CREATE INDEX IF NOT EXISTS idx_mod_removed_created_utc ON mod_removed (created_utc);
        """
        )
        conn.executescript(
            """CREATE TABLE IF NOT EXISTS reddit_removed (
            id VARCHAR(50) NOT NULL,
            username VARCHAR(20) NOT NULL,
            target VARCHAR(10),
            mod VARCHAR(20),
            post VARCHAR(10),
            created_utc INTEGER,
            PRIMARY KEY (id)
            );
            CREATE INDEX IF NOT EXISTS idx_reddit_removed_username ON reddit_removed (username);
            CREATE INDEX IF NOT EXISTS idx_reddit_removed_created_utc ON reddit_removed (created_utc);
        """  # noqa: E501
        )
        conn.commit()
        return conn

    def _get_last(self, table: str) -> str:
        before = None
        query = self._conn.execute(f"SELECT id FROM {table} ORDER BY created_utc DESC LIMIT 1")
        for row in query:
            before = row[0]
        LOGGER.debug("Last %s in DB: %s", table, before)
        return before

    def download_banned(self) -> list[tuple[str, str, str, str]]:
        actions = []
        params = {"before": self._get_last("banned")}
        for action in self._sub.mod.log(action="banuser", limit=1001, params=params):
            actions.append(
                (
                    action.id,
                    action.target_author,
                    action.details,
                    action.created_utc,
                )
            )
        return actions

    def download_reddit(self) -> list[tuple[str, str, str, str, str, str]]:
        actions = []
        params = {"before": self._get_last("reddit_removed")}
        for action in self._sub.mod.log(mod="a", limit=1001, params=params):
            target = next(self._sub._reddit.info(fullnames=[action.target_fullname]))
            actions.append(
                (
                    action.id,
                    action.target_author,
                    action.target_fullname,
                    action.mod.name,
                    getattr(target, "link_id", target.fullname),
                    target.created_utc,
                )
            )
        return actions

    def download_removed(self) -> list[tuple[str, str, str, str, str]]:
        actions = []
        params = {"before": self._get_last("mod_removed")}
        for action in self._sub.mod.log(action="addremovalreason", limit=1001, params=params):
            target = next(self._sub._reddit.info(fullnames=[action.target_fullname]))
            actions.append(
                (
                    action.id,
                    action.target_author,
                    action.target_fullname,
                    getattr(target, "link_id", target.fullname),
                    target.created_utc,
                )
            )
        return actions

    def main(self) -> None:
        actions = self.download_banned()
        LOGGER.debug("Banned: %s", actions)
        self._conn.executemany("insert or replace into banned values (?,?,?,?)", actions)
        actions = self.download_removed()
        LOGGER.debug("Removed %s", actions)
        self._conn.executemany("insert or replace into mod_removed values (?,?,?,?,?)", actions)
        actions = self.download_reddit()
        LOGGER.debug("Reddit %s", actions)
        self._conn.executemany(
            "insert or replace into reddit_removed values (?,?,?,?,?,?)", actions
        )
        self._conn.commit()
        self._conn.close()


def main():
    """Provide the entry point to the user_since command."""
    parser = ArgParser(usage="usage: %(prog)s subreddit")
    parser.add_argument("subreddit", type=str, help="The display name of the subreddit")
    parser.add_argument(
        "--verbose",
        "-v",
        type=int,
        default=0,
        help="0 for disabled, 1 for info, more for debug",
    )
    options = parser.parse_args()

    if options.verbose == 1:
        LOGGER.setLevel(logging.INFO)
    elif options.verbose > 1:
        LOGGER.setLevel(logging.DEBUG)
    else:
        LOGGER.setLevel(logging.NOTSET)
    LOGGER.addHandler(logging.StreamHandler())
    RedditMonitor(options.subreddit).main()


if __name__ == "__main__":
    main()

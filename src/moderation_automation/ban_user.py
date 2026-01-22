import logging
import sqlite3
from argparse import ArgumentParser as ArgParser
from datetime import UTC, datetime, timedelta
from pathlib import Path

import praw
from praw.exceptions import RedditAPIException

LOGGER = logging.getLogger(__file__)


class RedditBan:
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

        def dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row):
            fields = [column[0] for column in cursor.description]
            return {key: value for key, value in zip(fields, row, strict=True)}

        conn.row_factory = dict_factory
        return conn

    def _get_query(self, filename: str) -> str:
        with open(Path(__file__).parent / Path(filename)) as qin:
            query_lines = qin.readlines()
            query_lines = [row for row in query_lines if not row.strip().startswith("--")]
        return "\n".join(query_lines)

    def main(self) -> None:
        query = self._get_query("potential.sql")
        rows = self._conn.execute(query)
        for row in rows:
            LOGGER.debug("Candidate %s", row)
            mod_val = (
                (float(row["mod_count"]) ** 2 + row["mod_count_post"] ** 2) / (2 * row["mod_count"])
                if row["mod_count"] > 0
                else 0
            )  # (a^2 + b^2)/(2 a)
            reddit_val = (
                (row["reddit_count"] ** 2 + row["reddit_count_post"] ** 2)
                / (2 * row["reddit_count"])
                if row["reddit_count"] > 0
                else 0
            )  # (a^2 + b^2)/(2 a)
            LOGGER.debug("Check %s = %f", row["username"], mod_val + reddit_val)
            if mod_val + reddit_val >= 4:
                LOGGER.info("Banning %s", row["username"])
                try:
                    self._sub.banned.add(
                        row["username"],
                        duration=self._duration(row["n_ban"]),
                        note="Autoban for Multiple remove",
                        ban_message=self._ban_message(
                            row["username"],
                            row["n_ban"],
                        ),
                    )
                except RedditAPIException as e:
                    if e.items and len(e.items) == 1:
                        api_e = e.items[0]
                        if api_e.error_type == "USER_DOESNT_EXIST":
                            LOGGER.warning("User %s does not exist", row["username"])
                            self._conn.execute(
                                "insert or replace into banned values (?,?,?,?)",
                                (
                                    datetime.now().timestamp(),
                                    row["username"],
                                    api_e.error_type,
                                    int((datetime.now() - timedelta(days=7)).timestamp()),
                                ),
                            )
                            continue
                        print("Exception banning ", row["username"], " : ", e.error_type)
                    raise e
        self._conn.commit()
        self._conn.close()

    def _duration(self, nban: int) -> int | None:
        if nban == 0:
            return 7
        if nban == 1:
            return 28
        return None

    def _ban_message(self, username: str, nban: int) -> str:
        txt = (
            f"Ciao u/{username}, sei stato bannato perché troppi tuoi messaggi sono stati rimossi."
        )
        txt += "\n\nEcco una lista:\n\n"
        query = self._get_query("removed_comments.sql")
        for row in self._conn.execute(query, (username, username)):
            timestamp = datetime.fromtimestamp(row["created_utc"], UTC).strftime("%H:%M del %d/%m")
            txt += (
                f"- [commento alle {timestamp}]"
                f"(/r/{self.subreddit}/comments/{row['post_id'][3:]}/_/{row['comment_id'][3:]})"
            )
            if row["reddit"] and row["reddit"] == "1":
                txt += " (rimosso dagli amministratori di Reddit)"
            txt += "\n"
        if nban > 0:
            if nban == 1:
                txt += f"\n\nATTENZIONE: Questo è il tuo ban numero {nban + 1}."
            else:
                txt += f"\n\nQuesto è il tuo ban numero {nban + 1}, quindi il provvedimento è definitivo."
        return txt


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
    RedditBan(options.subreddit).main()


if __name__ == "__main__":
    main()

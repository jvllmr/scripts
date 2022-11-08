from __future__ import annotations

import typing as t
from contextlib import contextmanager
from urllib.parse import urlencode

from rich.progress import MofNCompleteColumn, Progress
from steam.webauth import WebAuth as SteamClient

if t.TYPE_CHECKING:
    import requests

STEAM_ITEMS_SECTION_ID = 753
INVENTORY_CONTEXT_ID = 6
USER_NAME = "idieddude"
STEAM_PROFILE_ID = USER_NAME
ITEMS_IN_INVENTORY_COUNT = 5_000


@contextmanager
def steam_client():
    client = SteamClient(USER_NAME)
    client.cli_login()
    yield client


def get_items(session: requests.Session, steamid64: str):
    resp = session.get(
        f"https://steamcommunity.com/inventory/{steamid64}/{STEAM_ITEMS_SECTION_ID}/{INVENTORY_CONTEXT_ID}?count={ITEMS_IN_INVENTORY_COUNT}"  # noqa: E501
    )
    if resp.status_code != 200:
        raise Exception("Inventory could not be loaded")
    return resp.json()


def find_duplicates(items: dict[str, t.Any]):
    class_ids: set[str] = set()
    duplicates: set[tuple[str, str]] = set()
    for item in items["assets"]:
        if (classid := item["classid"]) in class_ids:
            duplicates.add((item["assetid"], classid))
        else:
            class_ids.add(classid)
    return duplicates


def get_item_description(items: dict[str, t.Any], classid: str):
    for item in items["descriptions"]:
        if item["classid"] == classid:
            return item


def main():
    with steam_client() as client:
        steamid64 = client.steam_id
        session = client.session
        session_id = client.session_id

        items = get_items(session, steamid64)
        duplicate_assetids = find_duplicates(items)
        with Progress(
            *Progress.get_default_columns(), MofNCompleteColumn()
        ) as progress:
            task = progress.add_task(
                "[cyan]Grinding gems...", total=len(duplicate_assetids)
            )
            completed = 0
            for assetid, classid in duplicate_assetids:
                item_desc = get_item_description(items, classid)
                if "owner_actions" in item_desc and "market_fee_app" in item_desc:
                    if "goo" not in item_desc["owner_actions"][-1]["link"].lower():
                        continue
                    data = {
                        "contextid": str(INVENTORY_CONTEXT_ID),
                        "assetid": assetid,
                        "sessionid": session_id,
                        "appid": str(item_desc["market_fee_app"]),
                    }
                    try:
                        data["goo_value_expected"] = session.get(
                            f"https://steamcommunity.com/id/{STEAM_PROFILE_ID}/ajaxgetgoovalue?{urlencode(data)}"  # noqa: E501
                        ).json()["goo_value"]
                    except Exception:
                        continue

                    headers = {
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:106.0) Gecko/20100101 Firefox/106.0",  # noqa: E501
                        "X-Requested-With": "XMLHttpRequest",
                        "Referer": f"https://steamcommunity.com/id/{STEAM_PROFILE_ID}/inventory/",
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "Origin": "https://steamcommunity.com",
                        "Host": "steamcommunity.com",
                    }

                    resp = session.post(
                        f"https://steamcommunity.com/id/{STEAM_PROFILE_ID}/ajaxgrindintogoo/",
                        data=data,
                        headers=headers,
                    )
                    assert resp.status_code == 200, (resp.status_code, resp.text, data)
                    completed += 1
                    progress.update(task, completed=completed)


if __name__ == "__main__":
    main()

'''
Authors: Columbia University Uncornered Team

The file will extract all rows from the table on shooting incidents that occured within a year

This script uses Playwright to automate a browser, navigate to the Boston shooting dashboard, and extract all rows from the table by simulating scrolling. 
The extracted data is saved to a CSV file.  

DO NOT MODIFY THIS FILE
'''

import time
import json
import re
import pandas as pd
from playwright.sync_api import sync_playwright

URL = "https://boston.maps.arcgis.com/apps/dashboards/dbd16dfec5b54734bd7d927b26b38a24"
OUTPUT_CSV = "boston_last_year_all_rows.csv"

def clean(text):
    return " ".join(text.split()).strip()

def all_contexts(page):
    return [page] + list(page.frames)

def find_and_click_table(page):
    for ctx in all_contexts(page):
        try:
            buttons = ctx.locator('div.tab-handle[role="button"]')
            for i in range(buttons.count()):
                btn = buttons.nth(i)
                txt = clean(btn.inner_text())
                if btn.is_visible() and "table" in txt.lower():
                    btn.click(force=True)
                    time.sleep(3)
                    return ctx
        except Exception:
            pass
    raise RuntimeError("Could not find the Table button.")

def get_current_timeframe(ctx):
    candidates = [
        '.date-selector-widget .font-light .text-ellipsis',
        '.date-selector-widget [title]',
        '.date-selector-widget span'
    ]
    for sel in candidates:
        try:
            loc = ctx.locator(sel)
            for i in range(loc.count()):
                txt = clean(loc.nth(i).inner_text())
                if txt and txt.lower() not in {"select a timeframe:"}:
                    return txt
        except Exception:
            pass
    return None

def open_timeframe_dropdown(ctx):
    candidates = [
        'div.date-selector-widget button.dropdown-toggle.selector-header',
        'div.date-selector-widget button.dropdown-toggle',
        'div.date-selector-widget button[aria-haspopup="true"]'
    ]
    for sel in candidates:
        try:
            btn = ctx.locator(sel).first
            if btn.count() > 0 and btn.is_visible():
                btn.click(force=True)
                time.sleep(1.5)
                return True
        except Exception:
            pass
    return False

def select_timeframe(ctx, label="Last Year"):
    current = get_current_timeframe(ctx)
    print(f"Current timeframe: {current}", flush=True)

    if current and current.strip().lower() == label.lower():
        print(f"Timeframe already set to {label}", flush=True)
        return True

    if not open_timeframe_dropdown(ctx):
        raise RuntimeError("Could not open timeframe dropdown.")

    option_patterns = [
        f'text="{label}"',
        f'text=/{re.escape(label)}/i'
    ]

    # Try several likely dropdown option selectors
    locators = [
        ctx.locator(f'text="{label}"'),
        ctx.get_by_text(label, exact=True),
        ctx.locator(f'span:has-text("{label}")'),
        ctx.locator(f'div:has-text("{label}")'),
        ctx.locator(f'li:has-text("{label}")'),
        ctx.locator(f'button:has-text("{label}")'),
        ctx.locator(f'[role="option"]:has-text("{label}")'),
        ctx.locator(f'[role="menuitem"]:has-text("{label}")'),
    ]

    for loc in locators:
        try:
            count = loc.count()
            for i in range(count):
                el = loc.nth(i)
                txt = clean(el.inner_text())
                if label.lower() in txt.lower() and el.is_visible():
                    el.click(force=True)
                    time.sleep(3)
                    return True
        except Exception:
            pass

    raise RuntimeError(f'Could not select timeframe option "{label}".')

def extract_visible_records(ctx):
    rows = ctx.locator('div.tabulator-row[role="row"]')
    records = []

    for i in range(rows.count()):
        row = rows.nth(i)
        cells = row.locator('div.tabulator-cell[role="gridcell"]')
        record = {}

        for j in range(cells.count()):
            cell = cells.nth(j)
            field = cell.get_attribute("tabulator-field") or f"col_{j}"

            value_el = cell.locator("div.value-container").first
            value = clean(value_el.inner_text()) if value_el.count() > 0 else ""
            record[field] = value

        if record:
            records.append(record)

    return records

def scroll_once(scroll_box, step=700):
    return scroll_box.evaluate("""
        (el, step) => {
            const before = el.scrollTop;
            el.scrollTop = Math.min(before + step, el.scrollHeight - el.clientHeight);
            return {
                before,
                after: el.scrollTop,
                scrollHeight: el.scrollHeight,
                clientHeight: el.clientHeight
            };
        }
    """, step)

def get_boston_last_year_df(save_csv=True, output_csv=OUTPUT_CSV):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        page = browser.new_page(viewport={"width": 1900, "height": 1200})

        print("Opening dashboard...", flush=True)
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        time.sleep(8)

        print("Opening table view...", flush=True)
        ctx = find_and_click_table(page)

        print("Selecting Last Year...", flush=True)
        select_timeframe(ctx, "Last Year")

        print("Waiting for table...", flush=True)
        ctx.wait_for_selector('div.tabulator-tableholder', timeout=20000)
        ctx.wait_for_selector('div.tabulator-row[role="row"]', timeout=20000)
        time.sleep(3)

        scroll_box = ctx.locator("div.tabulator-tableholder").first

        seen = {}
        stagnant_rounds = 0

        for round_num in range(1, 400):
            visible = extract_visible_records(ctx)

            before = len(seen)
            for rec in visible:
                key = json.dumps(rec, sort_keys=True)
                seen[key] = rec
            added = len(seen) - before

            moved = scroll_once(scroll_box, step=700)
            time.sleep(1.5)

            print(
                f"Round {round_num} | visible={len(visible)} | new={added} | "
                f"scrollTop {moved['before']} -> {moved['after']}",
                flush=True
            )

            if added == 0:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0

            at_bottom = moved["after"] >= moved["scrollHeight"] - moved["clientHeight"] - 2
            no_move = moved["after"] == moved["before"]

            if at_bottom or no_move or stagnant_rounds >= 6:
                final_visible = extract_visible_records(ctx)
                for rec in final_visible:
                    key = json.dumps(rec, sort_keys=True)
                    seen[key] = rec
                break

        browser.close()

    if not seen:
        raise RuntimeError("No records extracted.")

    df = pd.DataFrame(list(seen.values()))

    preferred_order = [
        "Incident_Num",
        "Shooting_Date",
        "Shooting_Type_V2",
        "Location",
        "NEIGHBORHOOD",
        "District",
        "Victim_Gender",
        "Victim_Race",
        "Victim_Ethnicity_NIBRS",
        "Age",
    ]
    cols = [c for c in preferred_order if c in df.columns] + [c for c in df.columns if c not in preferred_order]
    df = df[cols]

    if save_csv:
        df.to_csv(output_csv, index=False)

    return df


if __name__ == "__main__":
    df = get_boston_last_year_df(save_csv=True)
    print(f"Saved {len(df)} rows to {OUTPUT_CSV}", flush=True)
    print(df.head(), flush=True)
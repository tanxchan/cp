import aiosqlite
import asyncio
from datetime import datetime as dt 

# col names:(same as cookies)

# domain : text, 
# name : text
# value : text
# path : text
# expires : real
# httpOnly : bool
# secure : bool
# sameSite : text

cook_names = (
"name",
"value",
"domain",
"path",
"expires",
"httpOnly",
"secure",
"sameSite",)

# custom cols:
# studentID: int4 
# created: timestamp
# live: bool


# "class_section",
# "instr_info",
# "meet_days", = "M", "T", "W", "H", "F"
# "start_time",
# "end_time",
# "meet_location",
# "enrl_status",
# "finl_day",
# "finl_date",
# "finl_times",
# "srs_crs_no",
# "unt_range"

async def create_databases(conn):
    cursor = await conn.cursor()
    await conn.execute("PRAGMA foreign_keys = ON")
    # table of students /users
    await cursor.execute("CREATE TABLE IF NOT EXISTS cookie_jar (" \
    "   name TEXT NOT NULL, value TEXT NOT NULL, domain TEXT, path TEXT, expires REAL, httpOnly REAL, secure BOOL, sameSite TEXT," \
    "   studentID int4, created TIMESTAMP default CURRENT_TIMESTAMP, live BOOL,  PRIMARY KEY (name, value))")
    # table of searchkeys
    # await cursor.execute("CREATE TABLE IF NOT EXISTS searchkeys ()")
    # table of all classes known
    # await cursor.execute("CREATE TABLE IF NOT EXISTS CLASSES ()")
    # table of discussions with keys linking to their classes
    # table of classes watched by each user
    # table of prerequisites 

    # would need some sort of system to auto-drop and enroll, and track which classes to drop etc.
    # could just have users rank classes
    await cursor.close()

stale = {'name': '_shibsession_64656661756c7468747470733a2f2f62652e6d792e75636c612e6564752f73686962626f6c6574682d73702f', 
         'value': '_985d72e9beb0c5d9fcb23ad2175e13c9', 'domain': 'be.my.ucla.edu', 'path': '/', 'expires': -1, 'httpOnly': True, 'secure': False, 'sameSite': 'Lax'}

async def add_ck(conn, cookie, id=306734536, created = None, live = True):
    '''requires all parts of cookies, literally just copy from async_playwright'''
    if not created:
        created = dt.now().strftime("%Y-%m-%d %H:%M:%S")
    await conn.execute(f"INSERT INTO cookie_jar"\
                       f" ({', '.join([name for name in cook_names])}, studentID, created, live)" \
                       f"VALUES ({', '.join(["?" for name in cook_names])}, ?, ?, ?) ON CONFLICT(name, value) DO NOTHING", 
                       (*[cookie[name] for name in cook_names], id, created, live))

async def get_ck(conn, name = "shib.be", id=306734536):
    '''use shib.be and shib.sa as aliases for _shibsession_ keys \
    use iwe.26F for 2026 fall, etc.
    '''
    match name:
        case "shib.be":
            name = "_shibsession_64656661756c7468747470733a2f2f62652e6d792e75636c612e656475" \
            "2f73686962626f6c6574682d73702f"
        case "shib.sa":
            name = "_shibsession_64656661756c7468747470733a2f2f73612e75636c612e656475"
    cursor = await conn.cursor()
    if name.startswith("iwe"):
        term = name.split(".")[-1]
        await cursor.execute("SELECT name, value FROM cookie_jar " \
        "WHERE name LIKE 'iwe_term_enrollment%' AND value = ? AND studentID = ? " \
        "ORDER BY created DESC", (term, id))
    else:
        await cursor.execute("SELECT name, value FROM cookie_jar " \
        "WHERE live AND name = ? AND studentID = ? ORDER BY created DESC", (name, id))
    row = await cursor.fetchone()
    return dict(row) if row is not None else None

async def main():
    conn = await aiosqlite.connect('data/test.db')
    conn.row_factory = aiosqlite.Row
    await create_databases(conn)

    await conn.commit()
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
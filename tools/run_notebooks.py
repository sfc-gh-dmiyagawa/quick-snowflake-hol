"""Run every code cell of the HOL notebooks top-to-bottom against a real account.

Python cells run as-is (get_active_session is patched to a local Snowpark session).
%%sql -r <name> cells are executed through session.sql; results are stored under <name>.
"""
import os, sys, json, re, traceback, nbformat
from snowflake.snowpark import Session
import snowflake.snowpark.context as ctx

session = Session.builder.config("connection_name", os.environ.get("SNOWFLAKE_CONNECTION", "handson")).create()
ctx.get_active_session = lambda: session

ns = {}
fail = 0
for path in sys.argv[1:]:
    nb = nbformat.read(path, as_version=4)
    print(f"\n######## {path}")
    for i, c in enumerate(nb.cells):
        if c.cell_type != "code":
            continue
        src = c.source.replace("APPLY_DEFAULT_ROLE = True", "APPLY_DEFAULT_ROLE = False  # validation: keep user's default role")
        head = src.splitlines()[0][:70]
        try:
            if src.startswith("%%sql"):
                name = re.match(r"%%sql -r (\w+)", src).group(1)
                body = src.split("\n", 1)[1]
                # split multi-statement cells on ';' at line end (no ';' inside our $$ bodies)
                stmts = [s for s in re.split(r";\s*\n", body) if s.strip()]
                for s in stmts:
                    res = session.sql(s).collect()
                ns[name] = res
                print(f"[{i:02}] OK  sql:{name}  rows={len(res)}  first={str(res[0])[:140] if res else ''}")
            else:
                exec(compile(src, f"{path}:{i}", "exec"), ns)
                print(f"[{i:02}] OK  py: {head}")
        except Exception as e:
            fail += 1
            print(f"[{i:02}] FAIL {head}\n      {type(e).__name__}: {str(e)[:400]}")
print("\nFAILURES:", fail)

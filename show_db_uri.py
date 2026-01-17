from run_auth_wrapper import app
import os
uri = app.config['SQLALCHEMY_DATABASE_URI']
print("URI:", uri)
if uri.startswith("sqlite:///"):
    p = uri.split("sqlite:///")[-1]
    print("Resolved path:", os.path.abspath(p))

from flask import Flask

from routes.dashboard import dashboard
from routes.comments import comments


app = Flask(__name__)

app.register_blueprint(dashboard)
app.register_blueprint(comments)


if __name__ == "__main__":
    app.run(debug=True)
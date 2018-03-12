import time
import json
import re
from pymongo import MongoClient

from flask import Flask, render_template, g, request, redirect, url_for, jsonify, flash
from flask_login import LoginManager, current_user, login_user, login_required, logout_user

from models.battle import Battle, BattleFactory
from models.board import BoardFactory
from models.user import User
from models.db_utility import init_generate, id_clear, id_generate, auth_db
from models.app_utility import success, failure, field_checker

from config import db_config, app_config

db = MongoClient(host=db_config['host'], port=db_config['port'])[db_config['db_name']]
auth_db(db, db_config)
init_generate(db, ["battles", "users"])

app = Flask(__name__)
app.config['SECRET_KEY'] = app_config['secret_key']

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.anonymous_user = User.anonymous_user(db)

@login_manager.user_loader
def load_user(user_id):
    return User.load_from_id(db, user_id)


@app.route("/")
def index_page():
    return render_template("index.html")

@app.route("/battles")
def battles_page():
    return render_template("battles.html")

@app.route("/rank-list")
def userlist_page():
    pass

@app.route("/users")
def user_page():
    try:
        user_id = int(request.args.get("user_id"))
    except:
        return render_template("error.html", message="该用户不存在")

    user = User.load_from_id(db, user_id)
    if user is None:
        return render_template("error.html", message="该用户不存在")

    return render_template("user.html", target_user=user)

@app.route("/battle")
def battle_page():
    battle_id = request.args.get('battle_id')
    return render_template("battle.html")

@app.route("/api/users", methods=['GET', 'POST'])
def users():
    if request.method == 'GET':
        try:
            query = json.loads(request.args.get("query", ""))
            sort = json.loads(request.args.get("sort", "[]"))
        except Exception as e:
            return failure(repr(e))

        #remove password
        projection = {"password" : False}

        return success(id_clear(db.users.find(
            filter=query,
            projection=projection,
            sort=sort)))

    elif request.method == 'POST':
        request_json = request.get_json(force=True)

        check_res = field_checker(request_json, ['username', 'email', 'password'])
        if check_res is not None:
            return failure(check_res)

        user = User.create(
            db, 
            id_generate, 
            request_json['username'], 
            request_json['email'], 
            request_json['password']
        )
        if isinstance(user, str):
            return failure(user)
        login_user(user)

        return success(user.dump())

@app.route("/api/users/online", methods=['POST', 'DELETE'])
def login():
    if request.method == 'POST':
        request_json = request.get_json(force=True)
        user = User.load_from_email(db, request_json['email'])

        if user is None:
            return failure("user not exist")
        if not user.check_password(request_json['password']):
            return failure("password not correct")

        login_user(user)

        return success(user.dump())

    elif request.method == 'DELETE':
        logout_user()

        return success(current_user.dump())
        
@app.route("/api/boards/<string:boardType>", methods=['GET'])
def boards(boardType):
    return success(BoardFactory.getBoardData(boardType))

@app.route("/api/battles", methods=['GET', 'POST'])
def battles():
    if request.method == 'GET':
        #need config (condition, sort)
        return success(id_clear(db.battles.find()))

    elif request.method == 'POST':
        request_json = request.get_json(force=True)

        check_res = field_checker(request_json, ['battle_info', 'board_type'])
        if check_res is not None:
            return failure(check_res)

        battle = BattleFactory.create_battle(
            int(time.time()),
            request_json['battle_info'],
            request_json['board_type'],
            db
        )
        if isinstance(battle, str):
            return failure(battle) 
        return success({"id": battle.id})

@app.route("/api/battles/<int:battle_id>", methods=['GET', 'POST'])
def battle(battle_id):
    if request.method == 'GET':
        battle = BattleFactory.load_battle(battle_id, db)
        user_id = int(request.args.get('user_id'))

        if isinstance(battle, str):
            return failure(battle)

        return success(battle.get_state(int(time.time()), user_id))

    elif request.method == 'POST':
        #todo check user_id match player_id
        request_json = request.get_json(force=True)

        check_res = field_checker(request_json, ['player_id', 'piece_id', 'position'])
        if check_res is not None:
            return failure(check_res)

        battle.try_drop_piece(
            int(time.time()), 
            request_json['player_id'],
            request_json['piece_id'],
            request_json['position']
        )
        return jsonify(battle.get_state(int(time.time()), request_json['player_id']))

@app.route("/api/battles/<int:battle_id>/players/<int:player_id>", methods=['POST', 'DELETE'])
@login_required
def players(battle_id, player_id):
    if request.method == 'POST':
        request_json = request.get_json(force=True)
        check_res = field_checker(request_json, ['user_id'])
        if check_res is not None:
            return failure(check_res)

        battle = BattleFactory.load_battle(battle_id, db)
        
        if isinstance(battle, str):
            return failure(battle)

        user_id = request_json['user_id']
        result = battle.try_join_player(int(time.time()), player_id, user_id)
        return success(result)
    
    elif request.method == 'DELETE':
        #todo
        pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
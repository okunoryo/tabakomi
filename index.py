from flask import Flask, request, jsonify
from freq_word import analyze
from freq_word import get_user_profile_image
from freq_word import get_trends_from_latlng
from freq_word import post_tweet
import pymysql.cursors
import random

app = Flask(__name__)

RANGE = 0.001


@app.route('/')
def hello_world():
    return 'Hello World!'


@app.route('/get_user', methods=["POST"])
def get_user():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, twitter as screen_name, comment, sex, image from users where " + request.form['user_id'] + " = id")
    result = cur.fetchone()

    cur.execute("SELECT * from user_tags where user_id = %s",
                (request.form['user_id'],))
    tag_result = cur.fetchall()
    cur.close()
    conn.commit()
    conn.close()

    if result is None:
        return jsonify(result='')
    result['twitter'] = analyze(result['screen_name'])

    tags = []
    for r in tag_result:
        tags.append(r['name'])
    result['tags'] = tags

    return jsonify(result=result)


@app.route('/register_user', methods=["POST"])
def register_user():
    image = 'http://abs.twimg.com/sticky/default_profile_images/default_profile_' + \
            str(random.randint(0, 6)) + '_bigger.png'
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (name, password, image, sex) VALUES (%s, %s, %s, %s)",
                (request.form['name'], request.form['password'], image, request.form['sex']))
    conn.commit()
    cur.execute("SELECT id FROM users WHERE name = '" + request.form['name'] + "' and password = '" + request.form['password'] + "'")
    user = cur.fetchone()
    cur.execute("INSERT INTO `locations` (`user_id`, `position`) VALUES (%s, GeomFromText('POINT(0 0)'))", user['id'])
    cur.close()
    conn.commit()
    conn.close()
    return jsonify(user_id=user['id'])


@app.route('/register_profile', methods=["POST"])
def register_profile():
    conn = connect_db()
    cur = conn.cursor()
    image = None
    if request.form['twitter'] is not None:
        twitter = request.form['twitter']
        image = get_user_profile_image(twitter)
    else:
        twitter = ''
    if request.form['comment'] is not None:
        comment = request.form['comment']
    else:
        comment = ''

    if image is None:
        cur.execute("UPDATE users SET twitter = %s, comment = %s WHERE id = %s",
                    (twitter, comment, request.form['user_id']))
    else:
        cur.execute("UPDATE users SET twitter = %s, comment = %s, image = %s WHERE id = %s",
                    (twitter, comment, image, request.form['user_id']))
    conn.commit()
    cur.close()
    conn.close
    return jsonify(status='success')


@app.route('/post_location', methods=["POST"])
def post_location():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("update `locations` set position = GeomFromText('POINT(" + request.form['lng'] + " " + request.form['lat'] + ")') where user_id=%s", request.form['user_id'])
    conn.commit()
    cur.close()
    conn.close

    conn = connect_db()
    cur = conn.cursor()

    cur.execute("SELECT yahhos.id AS id, X(position) AS lng, Y(position) AS lat, users.name, comment, twitter as screen_name,  pushed_user_id, pushing_user_id, reply, sex, image FROM yahhos LEFT JOIN users ON yahhos.pushing_user_id = users.id WHERE pushed_user_id = " + request.form['user_id'])
    result = cur.fetchone()
    if result is not None:
        cur.execute("DELETE FROM yahhos WHERE id = %s", (result['id'],))

    if result is None:
        cur.close()
        conn.commit()
        conn.close
        return jsonify(result='')

    cur.execute("SELECT * from user_tags where user_id = %s",
                (result['pushing_user_id'],))
    tag_result = cur.fetchall()
    cur.close()
    conn.commit()
    conn.close

    result['twitter'] = analyze(result['screen_name'])

    tags = []
    for r in tag_result:
        tags.append(r['name'])
    result['tags'] = tags

    return jsonify(result=result)


@app.route('/get_near_location_users', methods=["POST"])
def get_near_location_users():
    conn = connect_db()
    cur = conn.cursor()

    lat1 = str(float(request.form['lat']) + RANGE)
    lng1 = str(float(request.form['lng']) - RANGE)
    lat2 = str(float(request.form['lat']) - RANGE)
    lng2 = str(float(request.form['lng']) + RANGE)
    cur.execute("SELECT name, user_id, Y(position) as lat, X(position) as lng, sex, image from locations LEFT JOIN users ON locations.user_id = users.id where user_id != " + request.form['user_id'] + " and MBRContains(GeomFromText('LINESTRING(" + lng1 +" " + lat1 + ","  +  lng2 + " " + lat2 + ")'), position)")
    result = cur.fetchall()
    cur.close()
    conn.commit()
    conn.close()
    return jsonify(locations=result)


@app.route('/push_yahho', methods=["POST"])
def push_yahho():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name from users where " + request.form['pushing_user_id'] + " = id")
    r = cur.fetchone()

    print("reply" in request.form)
    if "reply" in request.form:
        cur.execute("INSERT INTO yahhos (name, position,pushing_user_id,pushed_user_id,reply) VALUES (%s, GeomFromText('POINT(" + request.form['lat'] + " " + request.form['lng'] + ")')," + request.form['pushing_user_id'] + "," + request.form['pushed_user_id'] + ", true)", r['name'])
    else:
        cur.execute("INSERT INTO yahhos (name, position,pushing_user_id,pushed_user_id) VALUES (%s, GeomFromText('POINT(" + request.form['lat'] + " " + request.form['lng'] + ")')," + request.form['pushing_user_id'] + "," + request.form['pushed_user_id'] + ")", r['name'])

    cur.close()
    conn.commit()
    conn.close()
    return jsonify(status='success')


@app.route('/get_tags', methods=["POST"])
def get_tags():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT * from user_tags where user_id = %s",
                (request.form['user_id'],))
    result = cur.fetchall()
    cur.close()
    conn.commit()
    conn.close()
    user_tags = []
    for r in result:
        user_tags.append(r['name'])
    return jsonify(tags=TAGS, user_tags=user_tags)


@app.route('/set_tag', methods=["POST"])
def set_tag():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO user_tags (user_id, name) VALUES (%s, %s)",
                (request.form['user_id'], request.form['name']))
    cur.close()
    conn.commit()
    conn.close()
    return jsonify(status='success')


@app.route('/remove_tag', methods=["POST"])
def remove_tag():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM user_tags WHERE user_id = %s and name = %s",
                (request.form['user_id'], request.form['name']))
    cur.close()
    conn.commit()
    conn.close()
    return jsonify(status='success')


@app.route('/enter_ibeacon', methods=["POST"])
def enter_ibeacon():
    conn = connect_db()
    cur = conn.cursor()
    major = request.form['major'] if 'major' in request.form else ''
    if major == '':
        major = None
    minor = request.form['minor'] if 'minor' in request.form else ''
    if minor == '':
        minor = None
    cur.execute("INSERT INTO ibeacons (user_id, uuid, major, minor) VALUES (%s, %s, %s, %s)",
                (request.form['user_id'], request.form['uuid'], major, minor))
    cur.close()
    conn.commit()
    conn.close()
    return jsonify(status='success')


@app.route('/exit_ibeacon', methods=["POST"])
def exit_ibeacon():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM ibeacons WHERE user_id = %s",
                (request.form['user_id'],))
    cur.close()
    conn.commit()
    conn.close()
    return jsonify(status='success')


@app.route('/get_ibeacons', methods=["POST"])
def get_ibeacons():
    conn = connect_db()
    cur = conn.cursor()
    major = request.form['major'] if 'major' in request.form else ''
    if major == '':
        major = None
    minor = request.form['minor'] if 'minor' in request.form else ''
    if minor == '':
        minor = None
    cur.execute("SELECT user_id, name, comment, sex, image from ibeacons LEFT JOIN users ON ibeacons.user_id = users.id WHERE user_id != %s and uuid = %s and major = %s and minor = %s",
                (request.form['user_id'], request.form['uuid'], major, minor))
    result = cur.fetchall()
    cur.close()
    conn.commit()
    conn.close()
    return jsonify(result=result)


@app.route('/get_trends', methods=["POST"])
def get_trends():
    if 'lat' in request.form and 'lng' in request.form:
        trends = get_trends_from_latlng(request.form['lat'], request.form['lng'])
    else:
        trends = get_trends_from_latlng()
    return jsonify(trends=trends)


@app.route('/post_photo', methods=["POST"])
def post_photo():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, twitter as screen_name from users where id = %s OR id = %s",
                (request.form['user_id1'], request.form['user_id2']))
    u1 = cur.fetchone()
    u2 = cur.fetchone()
    cur.close()
    conn.commit()
    conn.close()
    name1 = u1['name'] if u1['screen_name'] == '' else '@' + u1['screen_name']
    name2 = u2['name'] if u2['screen_name'] == '' else '@' + u2['screen_name']
    if 'lat' in request.form and 'lng' in request.form:
        url = post_tweet(filename=request.files['photo'].filename,
                         filedata=request.files['photo'].stream,
                         name1=name1, name2=name2,
                         lat=request.form['lat'], lng=request.form['lng'])
    else:
        url = post_tweet(filename=request.files['photo'].filename,
                         filedata=request.files['photo'].stream,
                         name1=name1, name2=name2)

    conn = connect_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO photos (user_id1, user_id2, url) VALUES (%s, %s, %s)",
                (request.form['user_id1'], request.form['user_id2'], url))
    cur.close()
    conn.commit()
    conn.close()
    return jsonify(url=url)


TAGS = ['ゼロの使い魔', 'ルイズ', 'ヤマグチノボル', '珈琲貴族', '黒髪', '桃髪', '貧乳', '太もも',
        'ゼロ魔', 'ゼロ使']

HOST = '133.2.37.129'
# HOST = 'localhost'
USER = 'tabakomi'
PASSWD = 'tabakomitabakomi'
DB = 'tabakomi'
CHARSET = 'utf8'


def connect_db():
    return pymysql.connect(host=HOST,
                           user=USER,
                           passwd=PASSWD,
                           db=DB,
                           charset=CHARSET,
                           cursorclass=pymysql.cursors.DictCursor)


if __name__ == '__main__':
    app.run(host='localhost', port=8080, debug=True)
    # app.run()

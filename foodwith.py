from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from slack_sdk import WebClient
from datetime import datetime

import re
import os
import ssl
import requests
import sys
import platform


class SlackApi:
    def __init__(self, token):
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        self.client = WebClient(token=token, ssl=ssl_context)
        self.token = token
        self.bob_message = [
            "우린 먹으려고 일 합니다. 점심 맛있게 드세요! 😎",
            "오늘의 메뉴는 정말 맛있는 메뉴에요! 👍",
            "좋은 하루 되세요! 😁",
            "코드스토리의 자랑 지하1층 구내식당 😙",
            "이제 하루의 절반이 되었네요. 좀만 힘냅시다. 👊",
        ]

    def get_channel_id(self, channel_name):
        result = self.client.conversations_list()
        channels = result.data['channels']
        print(channels)
        channel = list(filter(lambda c: c['name'] == channel_name, channels))[0]
        channel_id = channel['id']

        return channel_id

    def upload_file(self, channel_id, file_path):
        self.client.files_upload(
            channels=channel_id,
            file=file_path,
            title="오늘의 메뉴",
            filetype="image"
        )

    # 일(day)에서 밥돌이의 메세지 배열의 수 만큼 모듈러 연산 하면 배열을 초과하지 않고 하루에 하나씩 돌면서 출력할 수 있다.
    def get_message_roundrobin(self):
        today = datetime.today()
        message_index = today.day % len(self.bob_message)

        return self.bob_message[0] if message_index == 0 else self.bob_message[message_index - 1]

    def post_message(self, channel_id):
        self.client.chat_postMessage(
            channel=channel_id,
            text='[ 밥돌이 ] 오늘의 메뉴 업데이트',
            blocks=[
                {
                    "type": "section",
                    "text": {
                        'type': 'plain_text',
                        'text': "[밥돌이] " + datetime.today().strftime("%Y/%m/%d") + " 지하1층 구내식당 정보입니다 :)"
                    },
                },
                {
                    "type": "section",
                    "text": {
                        'type': 'plain_text',
                        'text': self.get_message_roundrobin()
                    },
                }
            ]
        )


# google chrome 드라이버를 사용하기 위한 초기화 함수
def initialize_chrome_driver(connect_url):
    options = webdriver.ChromeOptions()
    platform_name = platform.system()

    # gui가 없는 linux환경에서는 아래와 같이 설정해줘야 함.
    if platform_name == 'Linux':
        options.add_argument('--disable-extensions')
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(url=connect_url)
    driver.implicitly_wait(10)

    return driver


# 슬랙 api를 사용하기 위한 초기화 함수
def initialize_slack(channel_name):
    try:
        slack = SlackApi(os.environ["SLACK_TOKEN"])
        bob_channel_id = slack.get_channel_id(channel_name)

        return {
            'use_channel_id': bob_channel_id,
            'slack_api': slack
        }
    except KeyError:
        print("SLACK_TOKEN을 환경변수로 설정하세요.")


# 푸드위드 카톡 채널에서 메뉴의 이미지를 가져온다
# 이 도메인의 경우 무조건 첫번째에 메뉴사진이 있기 때문에 0번째 배열에서 가져오면 된다.
def get_menu_image_url(driver, element_class_name):
    news = driver.find_elements_by_class_name(element_class_name)
    if len(news) == 0:
        return []

    style = news[0].get_attribute("style")
    # url('주소'); 형식에서 '주소' 문자열만 추출해옴
    url = re.findall('"([^"]*)"', style)

    return url


def download_image(image_url, file_name):
    r = requests.get(image_url, allow_redirects=True)
    open(file_name, 'wb').write(r.content)


def notify_daily_menu_to_slack(slack, file_name):
    slack_api = slack['slack_api']
    slack_api.post_message(channel_id=slack['use_channel_id'])
    slack_api.upload_file(slack['use_channel_id'], "./" + file_name)
    os.remove(file_name)


# 데이터를 얻어올 주소
FOODWITH_KAKAO_CHANNEL_URL = 'https://pf.kakao.com/_eAGqxb'
# url주소와 매핑이 되는지 확인하기위한 정규식
MATCH_REGEX_FOR_URL_FORMAT = '^(https?://)[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/[a-zA-Z0-9-_/.?=]*'


def main(argv):
    # 웹 드라이버 초기화
    driver = initialize_chrome_driver(FOODWITH_KAKAO_CHANNEL_URL)
    # 슬랙 api 초기화
    slack = initialize_slack('밥')
    # 메뉴 이미지 가져오기
    image_url = get_menu_image_url(driver, 'thume_item')

    if len(image_url) > 0:
        url = 'https:' + image_url[0]
        # 주소 형식이랑 매치가 되는지
        is_url_matched = re.compile(MATCH_REGEX_FOR_URL_FORMAT).match(url)

        if is_url_matched is not None:
            file_name = 'foodwith.jpeg'

            download_image(url, file_name)
            notify_daily_menu_to_slack(slack, file_name)


if __name__ == "__main__":
    main(sys.argv)

import requests
from bs4 import BeautifulSoup
import re
import os
import json
from tqdm import tqdm

BASE_URL = "https://docs.aws.amazon.com/service-authorization/latest/reference/"
ENTRY_URL = BASE_URL + "reference_policies_actions-resources-contextkeys.html"
OUTPUT_DIR = "aws_service_actions"

def safe_filename(name):
    # 替换非法文件名字符
    return re.sub(r'[\\/*?:"<>| ]', "_", name)

def get_service_links():
    resp = requests.get(ENTRY_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if re.match(r"^(\./)?list_.*\.html$", href):
            abs_href = BASE_URL + href.lstrip('./')
            links.append((text, abs_href))
    print(f"共发现 {len(links)} 个 service 链接")
    print(f"第一条：{links[0][0]}  {links[0][1]}")
    return links

def parse_actions_table(service_url):
    resp = requests.get(service_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        print("未找到 table")
        return []
    rows = table.find_all("tr")[1:]
    actions = []
    last_resource_types = []
    last_context_keys = []
    for row in rows:
        cols = row.find_all("td")
        if not cols or len(cols) < 2:
            continue
        action_name = cols[0].get_text(strip=True)
        description = cols[1].get_text(strip=True)
        access_level = cols[2].get_text(strip=True) if len(cols) > 2 else ""
        # Resource types
        resource_types = []
        if len(cols) > 3:
            resource_types = [x.strip() for x in cols[3].stripped_strings if x.strip()]
            if not resource_types:
                resource_types = last_resource_types
            else:
                last_resource_types = resource_types
        else:
            resource_types = last_resource_types
        # Condition keys
        context_keys = []
        if len(cols) > 4:
            context_keys = [x.strip() for x in cols[4].stripped_strings if x.strip()]
            if not context_keys:
                context_keys = last_context_keys
            else:
                last_context_keys = context_keys
        else:
            context_keys = last_context_keys
        # 文档链接
        doc_link = ""
        a_tag = cols[0].find("a", href=True)
        if a_tag and a_tag["href"].startswith("https://docs.aws.amazon.com/"):
            doc_link = a_tag["href"]
        actions.append({
            "actionName": action_name,
            "name": action_name,
            "actionGroups": [access_level] if access_level else [],
            "resourceTypes": resource_types,
            "contextKeysRef": context_keys,
            "description": description,
            "docPageRelative": doc_link
        })
    print(f"共发现 {len(actions)} 个 action")
    for i, act in enumerate(actions[:10]):
        print(f"{i+1}: {act['actionName']} - {act['description']}")
    return actions

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    service_links = get_service_links()
    for service_name, link in tqdm(service_links):
        print(f"爬取 {service_name} 开始...")
        try:
            actions = parse_actions_table(link)
            if actions:
                filename = safe_filename(service_name) + ".json"
                with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8") as f:
                    json.dump(actions, f, ensure_ascii=False, indent=4)
                print(f"爬取 {service_name} 成功，已保存到 {OUTPUT_DIR}/{filename}")
        except Exception as e:
            print(f"爬取 {service_name} 失败: {e}")
    print(f"所有服务已保存到 {OUTPUT_DIR} 文件夹下。")

def test_first_service_actions():
    # 获取所有 service 链接
    service_links = get_service_links()
    if not service_links:
        print("未获取到 service 链接")
        return
    # 只取第一个 service
    service_name, link = service_links[0]
    print(f"测试第一个 service: {service_name} {link}")
    actions = parse_actions_table(link)
    print(f"共获取到 {len(actions)} 个 action，前5个如下：")
    for act in actions[:5]:
        print(json.dumps(act, ensure_ascii=False, indent=2))

# 你可以在文件末尾加上：
if __name__ == "__main__":
    # main()
    test_first_service_actions()

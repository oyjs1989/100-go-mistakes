import requests
from bs4 import BeautifulSoup
import re
import os
import json
from tqdm import tqdm
import concurrent.futures

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

def get_service_prefix(soup):
    # 在正文中查找 service prefix
    text = soup.get_text()
    m = re.search(r"service prefix: ([a-zA-Z0-9_-]+)", text)
    if m:
        return m.group(1)
    return ""

def parse_actions_table(service_url):
    resp = requests.get(service_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    service_prefix = get_service_prefix(soup)
    table = soup.find("table")
    if not table:
        print("未找到 table")
        return []
    rows = table.find_all("tr")[1:]
    actions = []
    current_action = None
    rowspan_left = 0
    for row in rows:
        cols = row.find_all("td")
        if not cols:
            continue
        # 判断是否为新 action 的起始行
        if rowspan_left == 0:
            action_name = cols[0].get_text(strip=True)
            if not action_name:
                continue
            description = cols[1].get_text(strip=True)
            access_level = cols[2].get_text(strip=True)
            # 资源类型
            resource_types = []
            if len(cols) > 3:
                resource_types += [x.get_text(strip=True) for x in cols[3].find_all("a")]
            # 条件键
            context_keys = []
            if len(cols) > 4:
                context_keys += [x.get_text(strip=True) for x in cols[4].find_all("a")]
            # 文档链接
            doc_link = ""
            a_tag = cols[0].find("a", href=True)
            if a_tag and a_tag["href"].startswith("https://docs.aws.amazon.com/"):
                doc_link = a_tag["href"]
            current_action = {
                "actionName": action_name,
                "name": action_name,
                "actionGroups": [access_level] if access_level else [],
                "resourceTypes": resource_types,
                "contextKeysRef": context_keys,
                "description": description,
                "docPageRelative": doc_link
            }
            actions.append(current_action)
            rowspan = int(cols[0].get("rowspan", 1))
            rowspan_left = rowspan - 1
        else:
            # 补充行，合并资源类型和条件键
            if len(cols) > 2:
                if len(cols) > 3:
                    current_action["resourceTypes"] += [x.get_text(strip=True) for x in cols[3].find_all("a")]
                if len(cols) > 4:
                    current_action["contextKeysRef"] += [x.get_text(strip=True) for x in cols[4].find_all("a")]
            rowspan_left -= 1
    # 去重
    for act in actions:
        act["resourceTypes"] = list(set(act["resourceTypes"]))
        act["contextKeysRef"] = list(set(act["contextKeysRef"]))
    print(f"共发现 {len(actions)} 个 action")
    for i, act in enumerate(actions[:10]):
        print(f"{i+1}: {act['actionName']} - {act['description']}")
    return {"servicePrefix": service_prefix, "actions": actions}

def download_service(service_name, link):
    print(f"爬取 {service_name} 开始...")
    try:
        result = parse_actions_table(link)
        if result and result.get("actions"):
            service_prefix = result.get("servicePrefix") or safe_filename(service_name)
            filename = safe_filename(service_prefix) + ".json"
            with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
            print(f"爬取 {service_name}({service_prefix}) 成功，已保存到 {OUTPUT_DIR}/{filename}")
    except Exception as e:
        print(f"爬取 {service_name} 失败: {e}")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    service_links = get_service_links()
    max_workers = os.cpu_count() or 4
    print(f"使用 {max_workers} 个线程并行下载")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for service_name, link in service_links:
            futures.append(executor.submit(download_service, service_name, link))
        for future in concurrent.futures.as_completed(futures):
            pass
    print(f"所有服务已保存到 {OUTPUT_DIR} 文件夹下。")

def test_first_service_actions():
    # 获取所有 service 链接
    service_links = get_service_links()
    if not service_links:
        print("未获取到 service 链接")
        return
    # 只取第一个 service
    service_name, link = service_links[1]
    print(f"测试第一个 service: {service_name} {link}")
    actions = parse_actions_table(link)
    print(f"共获取到 {len(actions['actions'])} 个 action，前5个如下：")
    print(json.dumps(actions['actions'], ensure_ascii=False, indent=2))

# 你可以在文件末尾加上：
if __name__ == "__main__":
    main()
    # test_first_service_actions()

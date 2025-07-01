import requests

def get_book_info(book_id):
    url = f"https://api5-normal-sinfonlinec.fqnovel.com/reading/user/share/info/v?group_id={book_id}&aid=1967"
    response = requests.get(url)
    if response.text is None:
        raise Exception("获取书籍信息失败")
    
    response_data = response.json()
    if response_data.get("code") != 0:
        raise Exception("获取书籍信息失败: " + response_data.get("messages", "未知错误"))
    
    data = response_data.get("data", {})
    book_info = data.get("book_info", {})

    book_name = book_info.get("book_name", "未知书名")
    book_id = book_info.get("book_id", "未知ID")
    author = book_info.get("author", "未知作者")
    abstract = book_info.get("abstract", "无简介")

    return book_name, author, abstract


def get_chapters_from_api(book_id):
    """从API获取章节列表"""
    url = f"https://fanqienovel.com/api/reader/directory/detail?bookId={book_id}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"获取章节列表失败，状态码: {response.status_code}")
            return None

        data = response.json()
        if data.get("code") != 0:
            print(f"API返回错误: {data.get('message', '未知错误')}")
            return None

        chapters = []
        chapter_ids = data.get("data", {}).get("allItemIds", [])
        
        # 创建章节列表
        for idx, chapter_id in enumerate(chapter_ids):
            if not chapter_id:
                continue
                
            final_title = f"第{idx+1}章"
            
            chapters.append({
                "id": chapter_id,
                "title": final_title,
                "index": idx
            })
        
        return chapters
    except Exception as e:
        print(f"从API获取章节列表失败: {str(e)}")
        return None
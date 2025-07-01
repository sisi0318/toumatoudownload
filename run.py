import os
import sys
import signal
import threading
import time
from tqdm import tqdm
from api import get_book_info, get_chapters_from_api
from utils import FqVariable, FqReq, save_status, load_status, down_text
from config import CONFIG


def graceful_exit(save_path, downloaded, chapter_results, output_file_path, name, author_name, description, chapters):
    """优雅退出，保存已下载内容"""
    print("\n检测到程序中断，正在保存已下载内容...")
    write_downloaded_chapters_in_order(
        chapter_results, output_file_path, name, author_name, description, chapters, downloaded
    )
    save_status(save_path, downloaded)
    print(f"已保存 {len(downloaded)} 个章节的进度")
    sys.exit(0)


def write_downloaded_chapters_in_order(chapter_results, output_file_path, name, author_name, description, chapters, downloaded):
    """按章节顺序写入"""
    if not chapter_results:
        return
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(f"小说名: {name}\n作者: {author_name}\n内容简介: {description}\n\n")
        for idx in range(len(chapters)):
            if idx in chapter_results:
                result = chapter_results[idx]
                title = f'{result["base_title"]} {result["api_title"]}' if result["api_title"] else result["base_title"]
                f.write(f"{title}\n{result['content']}\n\n")
            elif chapters[idx]["id"] in downloaded:
                continue


def Run(book_id, save_path):
    """主下载流程"""
    chapters = []
    name = author_name = description = ''
    output_file_path = ''
    downloaded = set()
    chapter_results = {}
    lock = threading.Lock()

    def signal_handler(sig, frame):
        graceful_exit(save_path, downloaded, chapter_results, output_file_path, name, author_name, description, chapters)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        chapters = get_chapters_from_api(book_id)
        if not chapters:
            print("未找到任何章节，请检查小说ID是否正确。")
            return
        name, author_name, description = get_book_info(book_id)
        if not name:
            print("无法获取书籍信息，将使用默认名称")
            name = f"未知小说_{book_id}"
            author_name = "未知作者"
            description = "无简介"
        downloaded = load_status(save_path) or set()
        if downloaded:
            print(f"检测到您曾经下载过小说《{name}》。")
            user_input = input("是否需要再次下载？如果需要请输入1并回车，如果不需要请直接回车即可返回主程序：")
            if user_input != "1":
                print("已取消下载，返回主程序。")
                return
        todo_chapters = [ch for ch in chapters if ch["id"] not in downloaded]
        if not todo_chapters:
            print("所有章节已是最新，无需下载")
            return
        print(f"开始下载：《{name}》, 总章节数: {len(chapters)}, 待下载: {len(todo_chapters)}")
        os.makedirs(save_path, exist_ok=True)
        output_file_path = os.path.join(save_path, f"{name}.txt")
        if not os.path.exists(output_file_path):
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(f"小说名: {name}\n作者: {author_name}\n内容简介: {description}\n\n")
        success_count = 0
        failed_chapters = []
        var = FqVariable(
            CONFIG["official_api"]["install_id"],
            CONFIG["official_api"]["device_id"],
            CONFIG["official_api"]["aid"],
            CONFIG["official_api"]["update_version_code"]
        )
        client = FqReq(var)
        register_key = client.get_register_key()
        def batch_download_tasks(chapter_list):
            nonlocal success_count
            batch_size = 30
            for i in range(0, len(chapter_list), batch_size):
                batch = chapter_list[i:i+batch_size]
                ids = [ch["id"] for ch in batch]
                titles_contents = down_text(ids, book_id, client=client, register_key=register_key)
                for idx, ch in enumerate(batch):
                    chapter_title, content = (None, None)
                    if titles_contents and isinstance(titles_contents, list) and idx < len(titles_contents):
                        chapter_title, content = titles_contents[idx]
                    if content:
                        with lock:
                            chapter_results[ch["index"]] = {
                                "base_title": ch["title"],
                                "api_title": chapter_title,
                                "content": content
                            }
                            downloaded.add(ch["id"])
                            success_count += 1
                    else:
                        with lock:
                            failed_chapters.append(ch)
        attempt = 1
        while todo_chapters:
            print(f"\n第 {attempt} 次尝试，剩余 {len(todo_chapters)} 个章节...")
            attempt += 1
            current_batch = todo_chapters.copy()
            with tqdm(total=len(current_batch), desc="下载进度") as pbar:
                batch_size = 30
                for i in range(0, len(current_batch), batch_size):
                    batch = current_batch[i:i+batch_size]
                    batch_download_tasks(batch)
                    pbar.update(len(batch))
            write_downloaded_chapters_in_order(
                chapter_results, output_file_path, name, author_name, description, chapters, downloaded
            )
            save_status(save_path, downloaded)
            todo_chapters = failed_chapters.copy()
            failed_chapters = []
            if todo_chapters:
                time.sleep(1)
        print(f"下载完成！成功下载 {success_count} 个章节")
    except Exception as e:
        print(f"运行过程中发生错误: {str(e)}")
        if 'downloaded' in locals() and 'chapter_results' in locals():
            write_downloaded_chapters_in_order(
                chapter_results, output_file_path, name, author_name, description, chapters, downloaded
            )
            save_status(save_path, downloaded)


def main():
    while True:
        print("我是例子链接：https://fanqienovel.com/page/7276384138653862966?enter_from=stack-room")
        print("我是例子id：7276384138653862966")
        book_id = input("请输入小说ID（输入q退出）：").strip()
        if book_id.lower() == 'q':
            break
        save_path = input("保存路径（留空为当前目录）：").strip() or os.getcwd()
        try:
            Run(book_id, save_path)
        except Exception as e:
            print(f"运行错误: {str(e)}")
        print("\n" + "="*50 + "\n")


if __name__ == "__main__":
    main()
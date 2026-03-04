"""
Smart Append - Appends content to a file, optionally under a targeted Markdown header.
"""

import argparse
import os


def smart_append(file_path: str, content: str, target_header: str | None = None) -> str:
    """
    Append text to a file. Can append to the end or insert under a targeted header.

    Args:
        file_path: The path to the file.
        content: The text content to append.
        target_header: Optional Markdown header under which to insert.

    Returns:
        Status message describing the action taken.
    """
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            if target_header:
                f.write(f"{target_header}\n\n{content}\n")
            else:
                f.write(f"{content}\n")
        return f"File '{file_path}' created and content added."

    if not target_header:
        with open(file_path, "a", encoding="utf-8") as f:
            if os.path.getsize(file_path) > 0:
                f.write(f"\n{content}")
            else:
                f.write(content)
        return f"Content appended to the end of '{file_path}'."

    with open(file_path, encoding="utf-8") as f:
        lines = f.readlines()

    header_found = False
    insert_index = -1
    clean_target = target_header.strip()

    for i, line in enumerate(lines):
        if line.strip() == clean_target:
            header_found = True
            insert_index = i + 1
            break

    if header_found:
        if insert_index < len(lines) and lines[insert_index].strip() != "":
            new_content_block = f"\n{content}\n"
        else:
            new_content_block = f"{content}\n"
        lines.insert(insert_index, new_content_block)
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return f"Content inserted under header '{target_header}' in '{file_path}'."
    else:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n{target_header}\n\n{content}\n")
        return f"Header '{target_header}' not found. Created header and appended content."


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Append text to a file, optionally under a targeted Markdown header."
    )
    parser.add_argument("file_path", help="The absolute or relative path to the file.")
    parser.add_argument("content", help="The text content to append.")
    parser.add_argument(
        "--target_header",
        help="The Markdown header under which to insert.",
        default=None,
    )
    args = parser.parse_args()
    try:
        result = smart_append(args.file_path, args.content, args.target_header)
        print(result)
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

"""How a converted document is split into searchable passages.

Kept in its own module (no models, storage or database) so the retrieval
evaluation in eval/ chunks documents exactly like the worker does.
"""

from langchain_core.documents import Document as LcDocument
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

_header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
    strip_headers=False,
)
_recursive_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)


def chunk_markdown(markdown_text: str) -> list[str]:
    header_docs = _header_splitter.split_text(markdown_text)
    if not header_docs:
        header_docs = [LcDocument(page_content=markdown_text)]
    final_docs = _recursive_splitter.split_documents(header_docs)
    return [d.page_content for d in final_docs if d.page_content.strip()]

import sys
try:
    import langchain
    import langchain_community
    print(f"LangChain version: {langchain.__version__}")
    
    try:
        from langchain.retrievers import EnsembleRetriever
        print("Success: langchain.retrievers.EnsembleRetriever")
    except Exception as e:
        print(f"Failed: langchain.retrievers ({e})")

    try:
        from langchain_community.retrievers import EnsembleRetriever
        print("Success: langchain_community.retrievers.EnsembleRetriever")
    except Exception as e:
        print(f"Failed: langchain_community.retrievers ({e})")
        
    # 尝试暴力搜索
    import inspect
    from langchain import retrievers
    if hasattr(retrievers, 'EnsembleRetriever'):
        print("Found in langchain.retrievers module attribute")
    else:
        print("Not found in langchain.retrievers module attribute")

except Exception as e:
    print(f"Global Error: {e}")

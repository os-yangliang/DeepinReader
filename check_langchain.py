import sys
print(f"Python path: {sys.path}")
try:
    import langchain
    print(f"LangChain version: {langchain.__version__}")
    print(f"LangChain file: {langchain.__file__}")
    
    try:
        from langchain.retrievers import EnsembleRetriever
        print("Success: from langchain.retrievers import EnsembleRetriever")
    except ImportError as e:
        print(f"Failed: from langchain.retrievers import EnsembleRetriever ({e})")

    try:
        from langchain.retrievers.ensemble import EnsembleRetriever
        print("Success: from langchain.retrievers.ensemble import EnsembleRetriever")
    except ImportError as e:
        print(f"Failed: from langchain.retrievers.ensemble import EnsembleRetriever ({e})")
        
except ImportError as e:
    print(f"Failed to import langchain: {e}")

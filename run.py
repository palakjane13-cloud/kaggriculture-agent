import uvicorn

if __name__ == "__main__":
    print("Starting AI Todo Agent server...")
    print("Open http://127.0.0.1:8000 in your browser to interact.")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, app_dir="backend")

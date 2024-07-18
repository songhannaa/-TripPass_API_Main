all:
	uvicorn app:app --host 0.0.0.0 --port 3000 --reload &
kill:
	kill -9 `lsof -t -i :3000`
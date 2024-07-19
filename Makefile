all:
	uvicorn app:app --host 0.0.0.0 --port 3500 --reload &
kill:
	kill -9 `lsof -t -i :3500`
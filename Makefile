# Sina OS — دستورهای کوتاه
.PHONY: help run doctor test install providers tokens ask docker clean

help:
	@echo "make run        اجرای سینا (نصب خودکار بار اول)"
	@echo "make doctor     بررسی سلامت"
	@echo "make test       اجرای تست‌ها"
	@echo "make providers  فهرست سرویس‌های پشتیبانی‌شده"
	@echo "make tokens     سرویس‌های متصل"
	@echo "make docker     اجرا با داکر"
	@echo "make clean      پاک‌کردن محیط مجازی و داده‌ها"

run:
	python3 sina.py

doctor:
	python3 sina.py doctor

test:
	cd backend && python3 -m pytest -q

providers:
	cd backend && python3 -m app.cli providers

tokens:
	cd backend && python3 -m app.cli token list

ask:
	cd backend && python3 -m app.cli ask "$(Q)"

docker:
	docker compose -f docker-compose.oss.yml up -d --build

docker-down:
	docker compose -f docker-compose.oss.yml down

clean:
	rm -rf .venv backend/__pycache__ backend/.pytest_cache data

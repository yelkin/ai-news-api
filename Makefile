.PHONY: docker-build docker-run

docker-build:
	docker build -t ainews .

docker-run:
	docker run --rm ainews

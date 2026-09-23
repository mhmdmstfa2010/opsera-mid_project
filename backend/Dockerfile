# ─── Stage 1: build ──────────────────────────────────────────────────────────
# Compiles the Spring Boot fat JAR inside the image so the host needs no JDK.
FROM maven:3.8-eclipse-temurin-11 AS build
WORKDIR /src
COPY . .
# Reuse the host-independent dependency cache across rebuilds instead of
# re-downloading every artifact each time.
RUN --mount=type=cache,target=/root/.m2 \
    mvn -B -q -DskipTests package

# ─── Stage 2: runtime ───────────────────────────────────────────────────────
FROM adoptopenjdk/openjdk11:alpine-jre
LABEL maintainer="it18162738@my.sliit.lk"

# Deliberately NOT /app: docker-compose.yml bind-mounts ./backend over /app,
# which would shadow a jar placed there.
WORKDIR /opt/app
COPY --from=build /src/target/student-service-docker.jar app.jar

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]

# ─── Stage 1: build ──────────────────────────────────────────────────────────
# Compiles the Spring Boot fat JAR inside the image so the host needs no JDK.
# Java 17: Spring Boot 3.x requires it (and CI already builds with 17).
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /src
COPY . .
# Reuse the host-independent dependency cache across rebuilds instead of
# re-downloading every artifact each time.
RUN --mount=type=cache,target=/root/.m2 \
    mvn -B -q -DskipTests package

# ─── Stage 2: runtime ───────────────────────────────────────────────────────
# adoptopenjdk/openjdk11:alpine-jre was EOL (Alpine 3.14, JDK 11.0.27) and
# carried 70 High/Critical CVEs — Gate 4 (Grype) refuses it.
FROM eclipse-temurin:17-jre-alpine
LABEL maintainer="it18162738@my.sliit.lk"

# Refresh base OS packages so fixable CVEs that landed after the base image
# was published (e.g. libexpat) do not trip Gate 4.
RUN apk upgrade --no-cache

# Deliberately NOT /app: docker-compose.yml bind-mounts ./backend over /app,
# which would shadow a jar placed there.
WORKDIR /opt/app
COPY --from=build /src/target/student-service-docker.jar app.jar

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]

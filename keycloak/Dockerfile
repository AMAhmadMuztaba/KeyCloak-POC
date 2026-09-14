FROM maven:3.9.11-eclipse-temurin-21 AS provider-build
WORKDIR /provider
COPY providers/autom-post-password-org-selector/pom.xml ./
RUN mvn -q dependency:go-offline
COPY providers/autom-post-password-org-selector/src ./src
RUN mvn -q package -DskipTests

FROM quay.io/keycloak/keycloak:26.7.3
COPY --from=provider-build /provider/target/autom-post-password-org-selector-1.0.0.jar /opt/keycloak/providers/

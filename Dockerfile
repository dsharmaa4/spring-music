FROM openjdk:8-jdk

# Default gradle version in the above is v4.0.1 - waaaaay too old!
ENV GRADLE_HOME /opt/gradle
ENV GRADLE_VERSION 6.9

ARG GRADLE_DOWNLOAD_SHA256=765442b8069c6bee2ea70713861c027587591c6b1df2c857a23361512560894e
RUN set -o errexit -o nounset \
	&& echo "Downloading Gradle" \
	&& wget --no-verbose --output-document=gradle.zip "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" \
	\
	&& echo "Checking download hash" \
	&& echo "${GRADLE_DOWNLOAD_SHA256} *gradle.zip" | sha256sum --check - \
	\
	&& echo "Installing Gradle" \
	&& unzip gradle.zip \
	&& rm gradle.zip \
	&& mv "gradle-${GRADLE_VERSION}" "${GRADLE_HOME}/" \
	&& ln --symbolic "${GRADLE_HOME}/bin/gradle" /usr/bin/gradle \
	\
	&& echo "Adding gradle user and group" \
	&& groupadd --system --gid 1000 gradle \
	&& useradd --system --gid gradle --uid 1000 --shell /bin/bash --create-home gradle \
	&& mkdir /home/gradle/.gradle \
	&& chown --recursive gradle:gradle /home/gradle

COPY . /spring-music
WORKDIR /spring-music
# Value from WORKDIR name overrides the project name if it doesn't match, and thus the final JAR file name!

EXPOSE 4000

RUN gradle clean assemble \
	&& pwd && ls build/libs \
	&& mv build/libs/spring-music-1.0.jar /app.jar
# The above leaves the source code in place... larger container image size

CMD java -jar -Dspring.profiles.active="in-memory" -Dserver.port=4000 /app.jar
#CMD java -jar -Dspring.profiles.active="postgres" /app.jar
# The above represents configuration WITHIN the container binary. Naughty.

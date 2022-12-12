
---
layout: fink-science-portal
title: Doc Dockerfile
author: Quentin
---

			\\\ Dockerfile Documentation ///
	


	- Prerequies for Docker



*To install Docker :	https://docs.docker.com/get-docker/
	
* To  Clone the fink-science-portal repository on the local machine :	git clone https://github.com/astrolabsoftware/fink-science-portal.git



 

			\\\ Basic Command from Docker ///



docker ps					The docker ps command only shows running containers by default. We can notice The ID of each containers.

docker ps -a					To see all containers.

docker images					shows all top level images, their repository an tags, and their size.

docker build  <path> .				Build an image from Dockerfile in the current folder.

docker build -f <Dockerfile> -t <test> .	The -f option allows to write just the name of the file and -t option create a tag name of the build.

docker rm -f <ID_Docker>			Stop and remove a container with this command and his specify ID in order to update the application.

git branch <name>				To create a new branche in the current folder.

git add <file>					To add the new modification of the file on the git

git commit					This will launch a text editor prompting you for a commit message. After you've entered a message, save the file and close the editor to create the actual commit.

git commit - m "message"			

git push					To push this modifications on the server.




			\\\  DOCKERFILE EXPLICATION ///


FROM						The FROM instruction initializes a new build stage and sets the Base Image for subsequent instructions. As such, a valid Dockerfile must start
						with a FROM instruction

WORKDIR						The WORKDIR instruction sets the working directory for any RUN, CMD, ENTRYPOINT, COPY and ADD instructions that follow it in the Dockerfile. If the WORKDIR 
						doesn’t exist, it will be created even if it’s not used in any subsequent Dockerfile instruction.

RUN						The RUN instruction will execute any commands in a new layer on top of the current image and commit the results. The resulting
						committed image will be used for the next step in the Dockerfile.

ENV						The ENV instruction sets the environment variable <key> to the value <value>. This value will be in the environment for all subsequent instructions in the
						build stage and can be replaced inline in many as well.
						The value will be interpreted for other environment variables, so quote characters will be removed if they are not escaped

ADD						The ADD instruction copies new files, directories or remote file URLs from <src> and adds them to the filesystem of the image at the path <dest>.

ENTRYPOINT					An ENTRYPOINT allows you to configure a container that will run as an executable.


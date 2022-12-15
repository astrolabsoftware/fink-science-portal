# Dockerfile's Tutorial
Here is the Docker tutorial to develop your containers on your local machines.

Make sure you have docker installed : https://docs.docker.com/get-docker/


## Develop your Docker

Fistly, you have to clone the fink science portal on the server in your local machine.

```bash
git clone git@github.com:astrolabsoftware/fink-science-portal.git
```

Enter in this new Directory.

```bash
cd fink-science-portal
```

## build your Docker image

To build a docker image, you should use `sudo docker build -f <path/to/Dockerfile> -t <image name> <path destination of your image>`

Therefore, we currently use :

```bash
sudo docker build -f docker/Dockerfile -t fsp .
```
Note that the . is the current directory.

The default docker images will show all top level images, their repository and tags, and their size.

```bash
sudo docker images
```



## Run your docker

This is the documentation in order to run a command in a new container.

```bash
sudo docker run -it fsp
```

The `docker ps` command only shows running containers by default. We can notice The ID of each containers. 

```bash
sudo docker ps
```


If you have a problem during the running command, think to remove the `.bash_history` file.

```bash
ls -ltha
```
```bash
sudo rm .bash_history
```

Enter `exit` to get out of the container.

To stop and remove your container, type `sudo docker rm -f <id_of_container>`.


##

## Share modifications of your Docker

To see all the modifications of your folder, type `git status`.

And to edit theses changes, enter :
```bash
git add docker <file> .
```

```bash
git commit -m "new modifications of your dockerfile"
```
This will launch a text editor prompting you for a commit message. After you've entered a message, save the file and close the editor to create the actual commit.


To push this modifications on the server:

```bash
git push
```

### Additionnal Supports

https://docs.docker.com/engine/reference/commandline/build/ 

https://docs.docker.com/engine/reference/commandline/run/

https://docs.docker.com/engine/reference/commandline/images/

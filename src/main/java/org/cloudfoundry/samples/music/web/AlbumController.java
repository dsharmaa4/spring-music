package org.cloudfoundry.samples.music.web;

import org.cloudfoundry.samples.music.config.ai.MessageRetriever;
import org.cloudfoundry.samples.music.domain.Album;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import org.springframework.ai.client.Generation;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.repository.CrudRepository;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;

@RestController
@RequestMapping(value = "/albums")
public class AlbumController {
    private static final Logger logger = LoggerFactory.getLogger(AlbumController.class);
    private CrudRepository<Album, String> repository;
    private MessageRetriever messageRetriever;

    @Autowired
    public AlbumController(CrudRepository<Album, String> repository, MessageRetriever messageRetriever) {
        this.repository = repository;
        this.messageRetriever = messageRetriever;

    }

    @RequestMapping(method = RequestMethod.GET)
    public Iterable<Album> albums() {
        return repository.findAll();
    }

    @RequestMapping(method = RequestMethod.PUT)
    public Album add(@RequestBody @Valid Album album) {
        logger.info("Adding album " + album.getId());
        return repository.save(album);
    }

    @RequestMapping(method = RequestMethod.POST)
    public Album update(@RequestBody @Valid Album album) {
        logger.info("Updating album " + album.getId());
        return repository.save(album);
    }

    @RequestMapping(value = "/{id}", method = RequestMethod.GET)
    public Album getById(@PathVariable String id) {
        logger.info("Getting album " + id);
        return repository.findById(id).orElse(null);
    }

    @RequestMapping(value = "/{id}", method = RequestMethod.DELETE)
    public void deleteById(@PathVariable String id) {
        logger.info("Deleting album " + id);
        repository.deleteById(id);
    }

    //
    @GetMapping("/ai/rag")
    public Generation generate(
            @RequestParam(value = "message", defaultValue = "Suggest rock music albums?") String message) {
        return messageRetriever.retrieve(message);
    }

}
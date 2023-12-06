#!/bin/bash

sudo systemctl start 1kv-dump-chain.service
sudo systemctl start 1kv-dump-json.service
sudo systemctl start 1kv-score.service
sudo systemctl start 1kv-website.service


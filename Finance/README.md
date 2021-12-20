# Finance

## Description

This is a full-stack web application that uses the iexcloud API to simulate stock trades and render information about a user's fictional trading account.

## Usage

Install dependencies:

```
pip install -r requirements.txt
```

Run the programme:
To run the programme you need to register on iexcloud.io/cloud-login#/register/ to get an API key.

```
export FLASK_APP=application.py
export FLASH_DEBUG=1
export API_KEY=<value>
flask run
```

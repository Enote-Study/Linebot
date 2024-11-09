const express = require('express');
const line = require('@line/bot-sdk');

const config = {
  channelAccessToken: '9sxOHcENP35N4R1PlMOxaOrpoTASTCVUnX13e/xZ6gchuuzbF5H7cRWToUKupMxOcgDwgQXBm8Ld+3rB6VqBFht9nDYkT3CMsE1QamcEAnTzEYpwS7gKk3/lJsRfijeXqKAsyNWbScVMbxM9Nhet3QdB04t89/1O/w1cDnyilFU=',
  channelSecret: '6362624df36e0b65adbc2a9d2de691eb',
};

const app = express();

app.post('/webhook', line.middleware(config), (req, res) => {
  Promise.all(req.body.events.map(handleEvent))
    .then((result) => res.json(result))
    .catch((err) => {
      console.error(err);
      res.status(500).end();
    });
});

function handleEvent(event) {
  if (event.type !== 'message' || event.message.type !== 'text') {
    return Promise.resolve(null);
  }

  const echo = { type: 'text', text: event.message.text };
  return client.replyMessage(event.replyToken, echo);
}

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});

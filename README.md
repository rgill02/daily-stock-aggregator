<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<a name="readme-top"></a>



<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
-->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]



<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/rgill02/daily-stock-aggregator">
    <img src="https://imgs.xkcd.com/comics/engineer_syllogism.png" alt="Logo">
  </a>

<h3 align="center">Daily Stock Aggregator</h3>

  <p align="center">
    Collects daily stock data (open, high, low, close, volume) for a given set of stocks and aggregates them into one publisher.
    <br />
    <a href="https://github.com/rgill02/daily-stock-aggregator"><strong>Explore the docs (coming soon)»</strong></a>
    <br />
    <br />
    <a href="https://github.com/rgill02/daily-stock-aggregator">View Demo (coming soon)</a>
    ·
    <a href="https://github.com/rgill02/daily-stock-aggregator/issues">Report Bug</a>
    ·
    <a href="https://github.com/rgill02/daily-stock-aggregator/issues">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#motivation">Motivation</a></li>
        <li><a href="#high-level-overview">High Level Overview</a></li>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

<!--[![Product Name Screen Shot][product-screenshot]](https://github.com/rgill02/daily-stock-aggregator)-->

### Motivation

At some point or another many software engineers will want to try their hand at algorithmic trading. They think "I'm good at pattern recognition and programming. I could write an algorithm to suggest trades I should make or even automatically trade for me." Whether they trade with real or simulated money, succeed or fail, most will still have fun as trading can be seen as a form of puzzle gaming. I have now fallen into this trap and want to try my hand at algorithmic trading (at first just writing some tools to do some technical analysis to give me alerts), mainly just for fun. I don't want to be constantly glued to the screen making daily trades (day trading), nor do I want to buy and hold for the long term (position trading). I want something in the middle where I can spend a few minutes looking over data and charts a day and be in trades for days to weeks (swing trading). Therefore, I will mostly be operating on daily stock data. Many fast and good sources of this data are not free. I don't want to pay for anything while I'm just toying around and having fun (if I get more serious down the road, then I might be willing to pay for data, but not at first). Yahoo Finance can provide this data for free in the timeframe I need so I will be using that, but it comes with some caveats.

Yahoo Finance has an API that allows you to pull historical stock data for free, and there is a python library yfinance that provides a very easy to use interface to this API. However, Yahoo Finance's API has a rate limit of 2000 requests/hour/ip address, which yfinance does not take into account. I found myself writing a quick program to pull in stock data after every market close. Then I had to add rate limiting to it as I added more stocks. Then I copied my program and modified it to pull in data at end of every day (even weekdays and holidays) for cryptocurrencies when experimenting with that. Then I found myself making another version that pulls a limited set of stocks every hour for experimenting with hourly updates. Before long I had a mess of many versions of code doing a very similar job. The goal of this project is to clean up that mess for myself and others. That way others don't have to go through the boring task of writing a data collector and can get right to the fun stuff: the algorithmic trading.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### High Level Overview

You will give the scraper a list of market securities (only updated on days the US stock market is open, like AAPL) and daily securities (updated everyday regardless of if US stock market is open, like BTC) you want data for. Everyday a few minutes after 4 PM Eastern Time (US market close) a scraping run will start. It will pull in the days data for the desired daily securities. Every weekeday after market it close it will also pull the days data for every desired market security. However, you can change the scraper to run in "monthly" mode, "hourly" mode or any other timeframe you like (just be conscience of the rate limit). For example "hourly" would pull in hourly data every hour. The scraper will pull in this data while abiding by the rate limit. For every new piece of data that is pulled in, the scraper will publish this data over ZMQ in a PUB-SUB model. This will allow consumers of the data to start and stop listening as they please as well as be a local process on the same machine or a process running on a remote machine. Anything that consumes this data will subscribe to the publisher. A subscriber can range from a strategy that is analyzing the incoming data to a database that collects the data for later backtesting. This architecture can let you create different timeframe scrapers, or scrapers at different ip addresses to split the work and pull the data faster. If you then want this data from multiple sources you can just subscribe to all of said sources.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



### Built With

* [Yahoo Finance](https://finance.yahoo.com/)
* [yfinance](https://pypi.org/project/yfinance/)
* [ZeroMQ](https://zeromq.org/)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- GETTING STARTED -->
## Getting Started

There are two ways to get started using this library: you can either setup a scraper yourself or subscribe to mine (coming soon). Mine is a daily scraper located in New York that pulls updates for every stock and the following cryptocurrencies: TODO. If this works for you then subscribe and filter for only what you need. If you need different securities or a different time frame then you will have to run your own scraper.

### Prerequisites

If you are listening to my scraper then you only need to install the following libraries:
  ```sh
  pip install ?
  ```

If you are running your own scraper then install:
  ```sh
  pip install ?
  ```


<!-- USAGE EXAMPLES -->
## Usage

Use this space to show useful examples of how a project can be used. Additional screenshots, code examples and demos work well in this space. You may also link to more resources.

_For more examples, please refer to the [Documentation](https://github.com/rgill02/daily-stock-aggregator)_

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ROADMAP -->
## Roadmap

- [x] Implement Scraper
- [x] Launch My Daily Scraper - 157.230.14.139:21000
- [ ] Implement Listener
- [ ] Create user manual / tutorial
- [ ] Update README

See the [open issues](https://github.com/rgill02/daily-stock-aggregator/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## Contributing

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

If you find a bug you want to fix, please fork the repo and create a pull request. You can also simply open an issue with the tag "bug".

1. Fork the Project
2. Create your Bug Branch (`git checkout -b bug/BugFix`)
3. Commit your Changes (`git commit -m 'Add some BugFix'`)
4. Push to the Branch (`git push origin bug/BugFix`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTACT -->
## Contact

Ryan Gill - ryansoftwaredev@gmail.com

Project Link: [https://github.com/rgill02/daily-stock-aggregator](https://github.com/rgill02/daily-stock-aggregator)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* [README Template](https://github.com/othneildrew/Best-README-Template/tree/master)
* []()
* []()

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/github_username/repo_name.svg?style=for-the-badge
[contributors-url]: https://github.com/github_username/repo_name/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/github_username/repo_name.svg?style=for-the-badge
[forks-url]: https://github.com/github_username/repo_name/network/members
[stars-shield]: https://img.shields.io/github/stars/github_username/repo_name.svg?style=for-the-badge
[stars-url]: https://github.com/github_username/repo_name/stargazers
[issues-shield]: https://img.shields.io/github/issues/github_username/repo_name.svg?style=for-the-badge
[issues-url]: https://github.com/github_username/repo_name/issues
[license-shield]: https://img.shields.io/github/license/github_username/repo_name.svg?style=for-the-badge
[license-url]: https://github.com/github_username/repo_name/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/linkedin_username
[product-screenshot]: images/screenshot.png

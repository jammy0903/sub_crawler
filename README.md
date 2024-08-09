# subDomain_crawle
#서브도메인 및 하위페이지 크롤링 (옵션 가능)
## Prerequisites

- Python 3.7 or higher(최소 파이썬 3.7 이상)
- [Amass](https://github.com/OWASP/Amass) installed and added to PATH

## Setup

1. Clone the repository:
   ```
   git clone git@github.com:jammy0903/sub_crawler.git
   cd sub_crawler
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv env
   source env/bin/activate  # On Windows use `env\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Usage

Run the spider with:
파일명이.. amas / crtns / sub / only_crt 중 하나임
```
python amas.py <domain> [max_depth]
```

For example:
```
python crtns.py example.com 3
```

## Output

The results will be saved in a JSON file named `<domain>_analysis.json`.
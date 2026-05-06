# JHposture
  
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/driscollh)

A 2-dimensional pose-estimation software that runs locally on a computer CPU to track interpersonal posture.

컴퓨터 CPU에서 로컬로 실행되어 대인 간의 자세를 추적하는 2차원 자세 추정(Pose-estimation) 소프트웨어입니다.

## 🔔 Stay Updated / 최신 업데이트 받기
**Never miss a new feature or bug fix.** Click the **Watch** button at the top right of this GitHub page, select **Custom**, and check the box for **Releases**. GitHub will automatically send you an email notification whenever a new version of JHposture is published!

**새로운 기능이나 버그 수정을 놓치지 마세요.** 이 GitHub 페이지 우측 상단의 **Watch** 버튼을 클릭하고, **Custom**을 선택한 뒤 **Releases** 확인란에 체크해 주세요. OpenCap Offline의 새 버전이 배포될 때마다 GitHub에서 자동으로 이메일 알림을 보내드립니다!

## Prerequisites / 사전 요구 사항
* Python 3.9.25
* Git
* Anaconda or Miniconda

## Installation & Setup / 설치 및 설정

**ENG**

Due to a number of critical version dependencies, please ensure you complete the following install steps in order:

**1. Download the Code**  
Clone this repository to your local machine:  
`git clone https://github.com/driscollh/JHposture.git`

**2. Create a Python Environment**  
`conda create -n JHposture python=3.9 -y`  
`conda activate JHposture`  

**3. Install Python Packages**  
Navigate into the main folder and install the required Python environment packages,
`pip install --no-cache-dir -r requirements.txt`

**4. Create models folder**
Inside your main project folder, create a new subfolder named `models`

~ ~ ~

**한국어**

중요한 버전 의존성 문제들이 있으므로, 반드시 다음 설치 단계를 순서대로 완료해 주시기 바랍니다:

**1. 코드 다운로드**  
이 리포지토리를 로컬 컴퓨터에 복제(Clone)합니다:  
`git clone https://github.com/driscollh/JHposture.git`

**2. Python 환경 생성**  
`conda create -n JHposture python=3.9 -y`  
`conda activate JHposture`

**3. Python 패키지 설치**  
메인 폴더로 이동하여 필요한 Python 환경 패키지들을 설치합니다.
`pip install --no-cache-dir -r requirements.txt`

**4. models 폴더 생성**  
기본 프로젝트 폴더 안에 `models`라는 이름의 새 하위 폴더를 생성합니다.

## Usage / 사용 방법

**ENG** 

Once the environment is set up, you can launch the local processing by running the main Python script in your environment.

`JHposture.py` 

Please note, the first run requires an internet connection and will take a few minutes to download the AI weights

~ ~ ~

**한국어**

환경 설정이 완료되면, 해당 환경에서 메인 Python 스크립트를 실행하여 로컬 데이터 처리를 시작할 수 있습니다.

`python JHposture.py`

참고: 첫 실행 시에는 AI 가중치(weights)를 다운로드해야 하므로 인터넷 연결이 필요하며 몇 분 정도 소요될 수 있습니다.

## Acknowledgments and Licensing \ 감사의 말 및 라이선스   
* **License:** Distributed under the Apache 2.0 License.
* **라이선스**: Apache 2.0 라이선스에 따라 배포됩니다.

## Citation / 인용
If you use JHposture in your research or clinical workflow, please cite it using the following DOI:  
연구나 임상 워크플로우에서 JHposture를 사용하시는 경우, 다음 DOI를 사용하여 인용해 주세요:

**APA:**

**BibTeX:**
  

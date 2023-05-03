import re
from urllib.parse import urlparse, urljoin
import urllib.robotparser as urllib_rp
from bs4 import BeautifulSoup
from textProcessor import TextProcessor
from hashlib import sha256
from collections import defaultdict

TP = TextProcessor()

class TextSimilarityProcessor:  #class for hasing (getting the fingerprint) of the webpage text and
                                #comparing it against the last crawled webpage to detect traps
    last_url_hash = ""  #This class compares against the last file downloaded

    def get_fingerprint(resp):  #gets the 32-bit fingerprint
        text = resp.get_text(strip=True)    #this function only uses the test of the html file to generate the fingerprint
        text_freq = TP.computeWordFrequencies(TP.tokenize(text))

        # TODO: Add to reports word Frequencies / Longest page

        vector = [0] * 32
        for token, weight in text_freq.items():
            token_bit_hash = bin(int.from_bytes(sha256(token.encode()).digest(), 'big'))[10:42]    #generates a binary string for each token via
                                                                                                   #the sha256 hash function
        
            for i in range(32):     #if bit is 1, add the weight to the vector, otherwise subtract the weight
                if int(token_bit_hash[i]) == 1:
                    vector[i] += weight
                else:
                    vector[i] -= weight
        
        fingerprint = ''
        for i in vector:    #fingerprint is generated by making the nth bit 1 if the nth element in the vector is positive, 0 otherwise
            if i > 0:
                fingerprint += '1'
            else:
                fingerprint += '0'

        return fingerprint

    def check_similar(resp):
        fingerprint = TextSimilarityProcessor.get_fingerprint(resp)

        if TextSimilarityProcessor.last_url_hash == "":
            TextSimilarityProcessor.last_url_hash = fingerprint
            return False
        else:   #checks if the fingerprint of the given url is similar to the last url's fingerprint
            similar_count = 0
            for i in range(32):
                if int(fingerprint[i]) == int(TextSimilarityProcessor.last_url_hash[i]):
                    similar_count += 1
        
        TextSimilarityProcessor.last_url_hash = fingerprint
        return (similar_count / 32.0) > 0.9     #set the threshold at 0.9

class Robots:   #The Robots class checks if the url is allowed in their respective domain's robot.txt
    ics = urllib_rp.RobotFileParser()   #construct the RobotFileParser() object
    ics.set_url('https://www.ics.uci.edu/robots.txt')   #set the url of the robot.txt file
    ics.read()  #read the file
    cs = urllib_rp.RobotFileParser()
    cs.set_url('https://www.cs.uci.edu/robots.txt')
    cs.read()
    stat = urllib_rp.RobotFileParser()
    stat.set_url('https://www.stat.uci.edu/robots.txt')
    stat.read()
    informatics = urllib_rp.RobotFileParser()
    informatics.set_url('https://www.informatics.uci.edu/robots.txt')
    informatics.read()
    
    def check_robots(url, netloc):  #checks if url is allowed, given the url and its domain name
        if re.match(r".*\.ics\.uci\.edu.*", netloc):
            return Robots.ics.can_fetch('*', url)
        if re.match(r".*\.cs\.uci\.edu.*", netloc):
            return Robots.cs.can_fetch('*', url)
        if re.match(r".*\.stat\.uci\.edu.*", netloc):
            return Robots.stat.can_fetch('*', url)
        if re.match(r".*\.informatics\.uci\.edu.*", netloc):
            return Robots.informatics.can_fetch('*', url)

# This class will keep track of data needed for the report
class Report:
    longest_page = 0    # holds the longest page length
    word_freq = defaultdict(int)    # word frequencies seen so far
    sub_domains = set() # set of sub domains seen so far
    seen_urls = set()   # set of urls seen
    N = 0   # top N words frequencies that would be presented
    
    def __init__(self, N) -> None:
        self.N = N  # initilizes the amount of top words frequencies

    def get_unique_pages(self):
        return len(self.seen_urls)  # returns amount of unique pages seen
    
    def get_longest_page(self):
        return self.longest_page    # returns length of longest page
    
    def get_N_common_words(self):
        return TextProcessor.getNTokenAndFreq(self.word_freq, self.N)   # gets the top N words with highest frequency


    def get_sub_domains(self, url):
        parse_url = urlparse.urlparse(url).hostname.split('.')
        if len(parse_url) < 2: #checks if there is a subdomain
            return "" #If no subdomain return empty string NOT SURE IF YOU WANT TO RETURN ANYTHING BUT LEFT IT AS AN OPTION
        else:
            return parse_url[:-1].join('.') #returns subdomain only if it is there is one or multiple
                                    #If there is multiple subdomains return looks like "subdomain1.subdomain2" as of now


    def update_pages(self, url):
        self.seen_urls.add(url)     # adds a url to the url set of urls weve seen so far

    def update_longest_page(self, l):
        if l > self.longest_page:
            self.longest_page = l   # updates longest length page if new page length is bigger

    def update_sub_domains(self, sub):
        self.sub_domains.add(sub)   # adds sub domain to the set of sub domains we have seen so far

    def update_word_freq(self, wordFreq):
        for k, v in wordFreq.items():
            self.word_freq[k] += v  # update word freq of words weve seen so far with new words seen
        



def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content

    num_unique_link = 0 # To count number of unique links
    url_set = set() #set with hyperlink to return

    if 200 <= resp.status < 300 : #if status code is ok and it is a valid link
        soup = BeautifulSoup(resp.raw_response.content, 'lxml') #parser using beautiful soup
        if TextSimilarityProcessor.check_similar(soup) == False: # checks for text similarity against previously added links
            for link in soup.find_all('a'):
                extracted_url = link.get('href')
                if extracted_url is None:  #check if extracted_url is a None object
                    continue

                index = extracted_url.rfind('#')
                url_remove_fragment = extracted_url[:index] if index >= 0 else extracted_url #removes the fragment portion of url
            
                absolute_url = urljoin(url, url_remove_fragment) #converts relative urls to absolute urls
                url_set.add(absolute_url) #adds url to list

    # TODO: add absolute urls to Report class
    return list(url_set)
    #return list()

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        parsed = urlparse(url)
        if parsed.scheme not in set(["http", "https"]):
            return False
        if check_domain_robots(url, parsed):
            return not re.match(
                r".*\.(css|js|bmp|gif|jpe?g|ico"
                + r"|png|tiff?|mid|mp2|mp3|mp4"
                + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
                + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
                + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
                + r"|epub|dll|cnf|tgz|sha1|war|txt|json"
                + r"|thmx|mso|arff|rtf|jar|csv"
                + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())
        else:
            return False
    except TypeError:
        print ("TypeError for ", parsed)
        raise

def check_domain_robots(url, url_parse):
    # checks if the url is under one of the four domains and is disallowed by their robots.txt

    netloc = url_parse.netloc.lower()
    
    #checks if the hostname is one of the four valid domains. Then checks their robots.txt
    if re.match(r".*\.ics\.uci\.edu.*|.*\.cs\.uci\.edu.*|.*\.stat\.uci\.edu.*|.*\.informatics\.uci\.edu.*", netloc):
        return Robots.check_robots(url, netloc)
    return False

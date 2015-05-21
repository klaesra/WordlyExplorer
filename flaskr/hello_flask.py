#!/usr/bin/env python2

import flask
import solr # Trying to switch to urllib3 (or 2) instead
import urllib2
import json
import cgi, cgitb
import vincent
import matplotlib.pyplot as plt
import numpy as np
import cStringIO
import seaborn as sns
import codecs
import helper_scripts
import itertools

from itertools import islice
from flask import request

# Create the application.
APP = flask.Flask(__name__)

# Create connection to solr database
s = solr.SolrConnection('http://localhost:8983/solr/trustpilot_reviews')

# Use seaborn
sns.set()
#sns.set_context("talk")
# sns.palplot(sns.color_palette()) # This causes a bunch of error messages to be displayed...QPixmap: It is not safe to use pixmaps outside the GUI thread

country_codes, reverse_cc = helper_scripts.make_country_codes()


def make_age_bars():
    return


def hist_ages_gender(term, ages_men, ages_women, total_men, total_women, min_age=10, max_age=90, num_bins=9):

    fig = plt.figure() # Fig name just to be able to close it again
    plt.title('Age and gender distribution for:     ' + term + '')
    plt.xlabel('Age range')
    plt.ylabel('Number of people')

    male_sorted = np.array([value for (key, value) in sorted(ages_men.items())])
    female_sorted = np.array([value for (key, value) in sorted(ages_women.items())])
    total_male_sorted = np.array([float(value) for (key, value) in sorted(total_men.items())])
    total_female_sorted = np.array([float(value) for (key, value) in sorted(total_women.items())])

#    print male_sorted
#    print total_male_sorted
#    print male_sorted/total_male_sorted

    bar_width = 0.35
    displace = bar_width/2
    plt.bar(np.array(range(len(ages_men))) + displace, male_sorted/total_male_sorted, bar_width, align='edge', label='Male', color='b')
    plt.bar(np.array(range(len(ages_women))) + displace + bar_width, female_sorted/total_female_sorted, bar_width, align='edge', label='Female', color='g')
    plt.xticks(range(len(ages_men)), sorted(ages_men))

    plt.legend()
    plt.tight_layout()
    sio = cStringIO.StringIO()
    plt.savefig(sio, format="jpg")
    plt.close(fig) # Close figures to save mem
    return sio

def get_stats(responses, responsesM, responsesF):

    genders = responses.facet_counts[u'facet_fields'][u'gender']
    ages = responses.facet_counts[u'facet_ranges'][u'age'][u'counts']
    agesM = responsesM.facet_counts[u'facet_ranges'][u'age'][u'counts']
    agesF = responsesF.facet_counts[u'facet_ranges'][u'age'][u'counts']
    return ages, genders, agesM, agesF

def do_query(query):
    frstart = 10
    frend = 89
    frgap = 10
    country = reverse_cc[request.form['country'][-2:]]
    facet_fields=['gender', 'nuts-3']
    geofcph = '{!geofilt pt=55.676,12.568 sfield=location d=25}'
    geofaarhus = '{!geofilt pt=56.157,10.21 sfield=location d=25}'
    filterq = ['country:\"' + country + '\"']
    filterqM = ['country:\"' + country + '\"', 'gender:M']
    filterqF = ['country:\"' + country + '\"', 'gender:F']
    #print request.form['region']
    if request.form['region'] == 'cph':
        filterq.append(geofcph)
        filterqM.append(geofcph)
        filterqF.append(geofcph)
    elif request.form['region'] == 'aarhus':
        filterq.append(geofaarhus)
        filterqM.append(geofaarhus)
        filterqF.append(geofaarhus)
    response = s.query(query, rows=5, facet_limit=1000, facet_heatmap='location_rpt', facet_heatmap_format='png', facet='true', facet_range=['age'],
                       facet_heatmap_gridLevel=4, facet_heatmap_maxCells=2000000,
                       facet_range_start=frstart, facet_range_end=frend,
                       facet_range_gap=frgap, facet_field=facet_fields, fq=filterq)
    responseM = s.query(query, rows=5, facet='true', facet_range=['age'], facet_range_start=frstart, facet_range_end=frend,
                        facet_range_gap=frgap, facet_field=facet_fields, fq=filterqM)
    responseF = s.query(query, rows=5, facet='true', facet_range=['age'], facet_range_start=frstart, facet_range_end=frend,
                        facet_range_gap=frgap, facet_field=facet_fields, fq=filterqF)
    response_texts = [response_t['text'] for response_t in response]
    return (response_texts, response, responseM, responseF)


def term_to_query(term):
    return "text:" + term  # Remember to set which field to query on (text for review-centric, review for user-centric)

@APP.route('/')
def index():
    """ Displays the index page accessible at '/'
    """
    return flask.render_template('trustpilot.html', queries = [])

@APP.route('/results', methods=['POST'])
def show_results():
    """ Displays the results of our query at '/results'
    """
    query = "*:*" # Remember to set which field to query on (text for review-centric, review for user-centric)

    _, data, dataM, dataF = do_query(query)

    nuts3regions = [[nuts3, val] for nuts3, val in data.facet_counts[u'facet_fields'][u'nuts-3'].iteritems() if val > 0] # we dont want to run over all of the other countries

    #print data.facet_counts[u'facet_fields'][u'nuts-3']
    img = data.facet_counts[u'facet_heatmaps'][u'location_rpt']['counts_png']

    image_output = cStringIO.StringIO()
    image_output.write(img.decode('base64'))   # Write decoded image to buffer

    total_ages, total_gender, total_ageM, total_ageF = get_stats(data, dataM, dataF)

    num_responses = [0,0]
    response_texts = [[],[]]
    response_full = []
    responseM = []
    responseF = []
    term = ["", ""]
    # get searches
    if request.method == 'POST':
        for i in range(2):
            box = 'searchbox' + str(i+1)
            if request.form[box]: # Ensure we have input in the given text field
                term[i] = request.form[box]
                response_texts[i], response, respM, respF = do_query(term_to_query(term[i]))
                response_full.append(response)
                responseM.append(respM)
                responseF.append(respF)
                num_responses[i] = response.numFound

        print 'num_responses: ', num_responses
        ages = [0,0]
        genders = [dict, dict]
        agesM = [dict, dict]
        agesF = [dict, dict]
        for i in range(len(response_full)):
            ages[i], genders[i], agesM[i], agesF[i] = get_stats(response_full[i], responseM[i], responseF[i])


        # ages, genders = zip(get_stats(response_full[0]), get_stats(response_full[1]))

        age_gen_hist = []
        regionstats = [[],[]]
        for i in range(len(response_full)):
            age_gen_hist.append(hist_ages_gender(term[i], agesM[i], agesF[i], total_ageM, total_ageF))
            curRegion = response_full[i].facet_counts[u'facet_fields'][u'nuts-3']
            regionstats[i] = [[region[0], float(curRegion[region[0]])/region[1]] for region in nuts3regions]

        print regionstats

        while len(age_gen_hist) < 2:
            #age_gen_hist.append(cStringIO.StringIO()) # TODO: REMEMBER ME!
            age_gen_hist.append(image_output)

        genders = [[genders[i][u'M'], genders[i][u'F']] for i in range(len(response_full))]
        while len(genders) < 2:
            genders.append([0,0])




        # print 'this is a select: ', s.query('text:*', facet='true', facet_fields=['gender', 'age', 'location'], fq='gender:M')
        # print 'this is a select: ', s.query('text:*', facet='true', facet_fields=['gender', 'age', 'location'], fq='gender:F').numFound
        # print s.query('*:*', facet='true', facet_field=['gender', 'age', 'location']).facet_counts[u'facet_fields'][u'gender']

        # Attempt using urllib2
        connection = urllib2.urlopen('http://localhost:8983/solr/trustpilot_reviews/select?facet=true&q=*:*&wt=json&facet.heatmap.format=png&facet.heatmap=location_rpt&facet.field=gender&facet.field=city&facet.heatmap.gridLevel=3') #&facet.heatmap.geom=["8 54" TO "13 58"]')
        response = json.load(connection)

        print 'this many', response['facet_counts']['facet_heatmaps']['location_rpt'][-1], "documents found."

        img = response['facet_counts']['facet_heatmaps']['location_rpt'][-1]

        image_output = cStringIO.StringIO()
        image_output.write(img.decode('base64'))   # Write decoded image to buffer


        # ["8 54" TO "13 58"]


        return flask.render_template('show_results.html', responses = [response_texts[0], response_texts[1]],
                                     queries = [term[0], term[1]], distribution = num_responses,
                                     agegenhist0 = age_gen_hist[0], agegenhist1 = age_gen_hist[1],
                                     genders = genders, country = request.form['country'],
                                     region = request.form['region'])
    else:
        return flask.render_template('trustpilot.html', queries = [])

if __name__ == '__main__':
    APP.debug=True
    APP.run()

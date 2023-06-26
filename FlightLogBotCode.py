# importing packages
from telegram import *
from telegram.ext import *
import logging
import pandas as pd
import csv
import requests
import json
from json import loads, dumps
import os
from datetime import datetime
import tabulate
import io
from smtplib import SMTP
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pretty_html_table import build_table


# Importing logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


# Reading the main logbook file from s3
# S3 access details are specified in an objet s3
import boto3
s3 = boto3.resource(
    service_name = 's3',
    region_name='eu-west-2',
    aws_access_key_id = 'AWS_access_key_id',
    aws_secret_access_key = 'AWS_secret_access_key'
)



# We can then pull csv files created earlier from this s3 object
# We will pull the main logbook file now
obj = s3.Bucket('BUCKETNAME').Object('CSVNAME').get()
FlightLogBotData = pd.read_csv(obj['Body'], index_col=False)
FlightLogColumnNames = []
for col in FlightLogBotData.columns:
    FlightLogColumnNames.append(col)


    
# Token gives access to python-telegram-bot
TOKEN = 'BOTTOKEN'




# Specifying the stages of the conversation handlers
QUESTION, ANSWER1, ANSWER2, ANSWER3 = range(4)
AIRFIELDICAO = range(1)
AIRFIELDNAME = range(1)
DATE, REMOVE = range(2)



# Start function
# Calls ups an initial inline keyboard to ask the user what they wish to do
async def start(update, context):
    keyboard = [
    [
        InlineKeyboardButton('Update logbook', callback_data = 'update_logbook'),
        InlineKeyboardButton('Airfields visited list', callback_data='airfieldsVis')],

        [InlineKeyboardButton('Airfield Info Search - By ICAO', callback_data='airfieldsearchICAO'),
        InlineKeyboardButton('Airfield Info Search - By NAME', callback_data='airfieldsearchNAME')],

        [InlineKeyboardButton('Total Hours Flown', callback_data='totals'),
        InlineKeyboardButton('Show LogBook', callback_data = 'logbook')],

      [InlineKeyboardButton('Flight by Date', callback_data='dateflight')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Flight Log Bot 🛩️ \nConversations can be stopped 🚫 at any point by typing /cancel")
    await update.message.reply_text("Select an action 🔠", reply_markup=reply_markup)




# The user may choose to look at airfields visited
# This takes the data from the Flight log bot data file imported earlier
# It looks for unique values in the airfields flown To column
async def airfields(update, context):
  obj = s3.Bucket('BUCKETNAME').Object('CSVFILE').get()
  FlightLogBotAirfields = pd.read_csv(obj['Body'], index_col=False)
    try:
        query = update.callback_query
        await query.answer()
    except:
        pass
    else:
        Airfields = FlightLogBotAirfields['To'].unique()
        await update.effective_chat.send_message(text= f"Airfields visitied: {Airfields}")
        # The user can then choose to search for specific airfields if they wish
        keyboard = [
        [
        InlineKeyboardButton('Yes - airfield ICAO search', callback_data = 'airfieldsearchICAO'),
        InlineKeyboardButton('Yes - airfield Name search', callback_data = 'airfieldsearchNAME'),
        InlineKeyboardButton('No', callback_data='No'),
        ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.effective_chat.send_message("Would you like to search information about a specific airfield", reply_markup=reply_markup)



# The user can choose initially or after seeing their airfields Visited if they would like to search an airfield
# This function will allow them to search by airfield ICAO 
async def airfieldsearch (update, context):
    try:
        # Their first time in the function will bring them to this section
        # followed by the else section which will ask them the airfield ICAO
        query = update.callback_query
        await query.answer()
    except:
        try:
		# RAPID API was used for airfield info
            context.user_data['airfields ICAO'].append(update.message.text)
            url = "https://airport-info.p.rapidapi.com/airport"
            airfieldicao = context.user_data.get('airfields ICAO')
            airfieldicao = airfieldicao[-1]
            querystring = {"icao":airfieldicao}
            headers = {
	        "X-RapidAPI-Key": "KEYID",
	        "X-RapidAPI-Host": "API_HOST"
            }
            response = requests.get(url, headers=headers, params=querystring)
            response = response.json()
            test = response['iata']
            test = str(test)

            obj = s3.Bucket('BUCKETNAME').Object('airports.csv').get()
            airportsdata = pd.read_csv(obj['Body'], index_col=None)

            obj = s3.Bucket('BUCKETNAME').Object('runways.csv').get()
            runwaysdata = pd.read_csv(obj['Body'], index_col=None)
            
            mergeddata = pd.merge(airportsdata,runwaysdata, left_on = 'ident', right_on = 'airport_ident', how = 'inner')
            mergeddata = mergeddata[mergeddata["iata_code"].fillna('').str.contains(test)]

            mergeddata = mergeddata[["ident", "type", "name", "latitude_deg",
                                "longitude_deg", "elevation_ft", "iata_code", "he_ident", "length_ft", "width_ft", "surface", "home_link"]]
            mergeddata = mergeddata.to_json(orient='records')
            mergeddata = loads(mergeddata)
            await update.effective_chat.send_message(json.dumps(mergeddata, indent = 1))
        except:
            try:
		    # Rapid API
		    # Rapid API rovide the code used here
                context.user_data['airfields ICAO'].append(update.message.text)
                url = "https://airport-info.p.rapidapi.com/airport"
                airfieldicao = context.user_data.get('airfields ICAO')
                airfieldicao = airfieldicao[-1]
                querystring = {"icao":airfieldicao}
                headers = {
	            "X-RapidAPI-Key": "Rapid API key",
	            "X-RapidAPI-Host": "Rapid API host URL"
                }
                response = requests.get(url, headers=headers, params=querystring)
                response = response.json()

                await update.effective_chat.send_message(json.dumps(response, indent = 1))
                await update.effective_chat.send_message("At this time we cannot provide anymore information about this airfield")
                
            except:
                await update.effective_chat.send_message("Our database does is sourced from different places \nIt may have missing data \nPlease ensure the code is entered correctly or try another code")

    else:
        context.user_data.update({'airfields ICAO':[]})

    await update.effective_chat.send_message(text = 'Please pass the airport ICAO code')
    return AIRFIELDICAO




# Airfield search can also be conducted by name
async def airfieldsearchname (update, context):
    try:
        query = update.callback_query
        await query.answer()
    except:
        context.user_data['airfields names'].append(update.message.text)
        airfieldname = context.user_data.get('airfields names')
        airfieldname = airfieldname[-1]
        obj = s3.Bucket('BUCKETNAME').Object('airports.csv').get()
        airportsdata = pd.read_csv(obj['Body'], index_col=None)

        obj = s3.Bucket('BUCKETNAME').Object('runways.csv').get()
        runwaysdata = pd.read_csv(obj['Body'], index_col=None)
        mergeddata = pd.merge(airportsdata,runwaysdata, left_on = 'ident', right_on = 'airport_ident', how = 'inner')
        mergeddata = mergeddata[mergeddata["name"].str.contains(airfieldname)]

        mergeddata = mergeddata[["ident", "type", "name", "latitude_deg",
                             "longitude_deg", "elevation_ft", "iata_code", "he_ident", "length_ft", "width_ft", "surface", "home_link"]]
        mergeddata = mergeddata.to_json(orient='records')
        mergeddata = loads(mergeddata)
        try:
            await update.effective_chat.send_message(json.dumps(mergeddata, indent = 1))
        except:
            await update.effective_chat.send_message("Too many results, \nPlease refine your search")
            
    else:
        
        context.user_data.update({'airfields names': []})

    await update.effective_chat.send_message(text = 'Please pass the airport Name')
    return AIRFIELDNAME




# users can quickly look at past flights by date, and if needed delete these flights
async def dateflightsearch(update, context):
  obj = s3.Bucket('BUCKETNAME').Object('LOGCSV').get()
  DateSearchData = pd.read_csv(obj['Body'], index_col=False)
  try:
    query = update.callback_query
    await query.answer()
  except:
    context.user_data['datesearch'].append(update.message.text)
    date = context.user_data.get('datesearch')
    date=pd.Series(date, dtype='string')
    date = pd.to_datetime(date, dayfirst = True).dt.date
    date = date
    date = date.iloc[-1]
    date = str(date)
    await update.effective_chat.send_message(f"{DateSearchData.loc[DateSearchData['Date']==date]}")
    keyboard = [
    [
    InlineKeyboardButton('yes', callback_data = 'yes'),
    InlineKeyboardButton('no', callback_data='no'),
    ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_chat.send_message(text = "Would you like to delete this row?", reply_markup = reply_markup)
    return REMOVE
  else:
    context.user_data.update({'datesearch': []})
  await update.effective_chat.send_message('Please enter a date to search your logbook')
  return DATE
  



# Part of the flight date search conversation handler
async def remove(update, context):
  obj = s3.Bucket('BUCKETNAME').Object('LOGCSV').get()
  DateSearchData = pd.read_csv(obj['Body'], index_col=False)
  date = context.user_data.get('datesearch')
  date=pd.Series(date, dtype='string')
  date = pd.to_datetime(date, dayfirst = True).dt.date
  date = date
  date = date.iloc[-1]
  date = str(date)
  DateSearchData = DateSearchData.loc[DateSearchData['Date']!=date]
  print(DateSearchData)
  DateSearchData.to_csv('LOGCSV', index = False)
  s3.Bucket('BUCKETNAME').upload_file(Filename='LOGCSV', Key='LOGCSV')
  await update.effective_chat.send_message('Row removed') 
  return ConversationHandler.END
    

  




# Main function for updating the flight logbook
async def update_logbook(update, context):
    try:
        query = update.callback_query
        await query.answer()
    except:
        # Not the first time in the function
        context.user_data['answers'].append(update.message.text)
        if context.user_data.get('index') == len(FlightLogColumnNames):
            print(context.user_data['answers'])

            keyboard = [
            [
            InlineKeyboardButton('yes', callback_data = 'yes'),
            InlineKeyboardButton('no', callback_data='no'),
            ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.effective_chat.send_message(
                text = f"You have entered the answers below, are these correct {context.user_data['answers']}", reply_markup = reply_markup
            )
            return ANSWER1        
    else:
        # First time in the function
        context.user_data.clear()
        context.user_data.update({'index': 0, 'answers': []})
    
    index = context.user_data.get('index')

    await update.effective_chat.send_message(
        text = f"Enter: {FlightLogColumnNames[index]},\nArrival and Departure time should be in the format: \nHH:MM:SS"
    )

    context.user_data.update({'index': index + 1})

    return QUESTION



# Once questions have gathered all teh information for the flight log book the answers are updated to a pandas dataframe which can then be saved as a csv file
async def updatecsv(update, context):
    try:
        query = update.callback_query
        await query.answer()
    except:
        return ConversationHandler.END
    else:
        try:
            await update.effective_chat.send_message('Answers have been entered correctly')
            df1 = pd.DataFrame(columns = FlightLogColumnNames)
            answers = context.user_data['answers']
            df1.loc[len(df1)] = answers

            df1['Date'] = pd.to_datetime(df1['Date'], dayfirst = True).dt.date
            df1['Departure Time']= pd.to_datetime(df1['Departure Time'], format = 'mixed').dt.time
            df1['Arrival Time']= pd.to_datetime(df1['Arrival Time'], format = 'mixed').dt.time
            df1['P1 - Day']= pd.to_timedelta(df1['P1 - Day'])
            df1['P2 - Day']= pd.to_timedelta(df1['P2 - Day'])
            df1['Dual - Day']= pd.to_timedelta(df1['Dual - Day'])
            df1['P1 - Night']= pd.to_timedelta(df1['P1 - Night'])
            df1['P2 - Night']= pd.to_timedelta(df1['P2 - Night'])
            df1['Dual - Night']= pd.to_timedelta(df1['Dual - Night'])

            obj = s3.Bucket('BUCKETNAME').Object('LOGCSV').get()
            FlightLogBotDataNew = pd.read_csv(obj['Body'], index_col=False)
        
            pd.concat([FlightLogBotDataNew, df1]).to_csv('LOGCSV', index = False)
            print(pd.read_csv('LOGCSV.csv'))
            s3.Bucket('cessna-152').upload_file(Filename='LOGCSV', Key='LOGCSV')

            keyboard = [
            [
            InlineKeyboardButton('Yes', callback_data = 'yes'),
            InlineKeyboardButton('No', callback_data='no'),
            InlineKeyboardButton('Add another Entry', callback_data='addanother'),
            ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.effective_chat.send_message(
                text = f"The Log Book has been updated. Would you like to see the totals list?", reply_markup = reply_markup
            )
            return ANSWER3
        except:
            await update.effective_chat.send_message(
                text = 'Answers have not been filled out correctly.'
            )
            context.user_data.clear()
            keyboard = [
            [
            InlineKeyboardButton('Yes', callback_data = 'yes'),
            InlineKeyboardButton('No', callback_data='no'),
            ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.effective_chat.send_message("Would you like to retry?", reply_markup=reply_markup)

            return QUESTION

        
    

# Totals function allows users to idenitfy the total hours conducted acting as each different type of flight crew
async def totals(update, context):
    try:
        query = update.callback_query
        await query.answer()
    except:
        return ConversationHandler.END
    else:
        await update.effective_chat.send_message('Totals selected')
        obj = s3.Bucket('BUCKETNAME').Object('LOGCSV').get()
        Totals = pd.read_csv(obj['Body'], index_col=False)
        Totals = Totals.filter(regex='Day|Night')
        Totals = Totals/pd.Timedelta(hours = 1)
        Totals = Totals.sum()
        await update.effective_chat.send_message(
            text = f"Totals are as shown: {Totals}"
        )
        return ConversationHandler.END

async def cancel(update, context):
    await update.effective_chat.send_message("Restart the bot with /start.")
    return ConversationHandler.END        




# The user can then send their logbook in a html table to any email address
def send_mail(body):
    message = MIMEMultipart()
    message['Subject'] = 'LogBook'
    message['From'] = 'email'
    message['To'] = 'email'

    body_content = body
    message.attach(MIMEText(body_content, "html"))
    msg_body = message.as_string()

    server = SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(message['From'], 'iegwhbpnetekqatz')
    server.sendmail(message['From'], message['To'], msg_body)
    server.quit()

def send_list():
    obj = s3.Bucket('BUCKETNAME').Object('LOGCSV').get()
    LogEmail= pd.read_csv(obj['Body'], index_col=False)
    output = build_table(LogEmail, 'blue_light')
    send_mail(output)




# part of the sending logbook flow of work
async def LogBook(update, context):
    send_list()
    await update.effective_chat.send_message('A logbook has been emailed to you')




def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))

    conv_updateLogBook = ConversationHandler(
        entry_points = [CallbackQueryHandler(update_logbook, pattern = 'update_logbook')],
        states = {
            QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_logbook), CallbackQueryHandler(update_logbook, pattern = 'yes'), CallbackQueryHandler(cancel, pattern = 'no')],
            ANSWER1: [CallbackQueryHandler(updatecsv, pattern = 'yes')],
            ANSWER2: [MessageHandler(filters.TEXT & ~filters.COMMAND, updatecsv)],
            ANSWER3: [CallbackQueryHandler(totals, pattern = 'yes'), CallbackQueryHandler(update_logbook, pattern = 'addanother'), CallbackQueryHandler(cancel, pattern = 'no')]

        },
        fallbacks = [CommandHandler("cancel", cancel)]
    )   



    conv_airfieldsearchICAO = ConversationHandler(
        entry_points = [CallbackQueryHandler(airfieldsearch, pattern = 'airfieldsearchICAO')],
        states = {
            AIRFIELDICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, airfieldsearch)],
        },
        fallbacks = [CommandHandler("cancel", cancel)]
    )




    conv_airfieldsearchNAME = ConversationHandler(
        entry_points = [CallbackQueryHandler(airfieldsearchname, pattern = 'airfieldsearchNAME')],
        states = {
            AIRFIELDNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, airfieldsearchname)],
        },
        fallbacks = [CommandHandler("cancel", cancel)]
    )

    conv_datesearch = ConversationHandler(
      entry_points=
      [CallbackQueryHandler(dateflightsearch, pattern = 'dateflight')],
      states = {
        DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, dateflightsearch)],
        REMOVE: [CallbackQueryHandler(remove, pattern = 'yes'), CallbackQueryHandler(cancel, pattern = 'no')]
      },
      fallbacks = [CommandHandler('cancel', cancel)]
    )

    # application.add_handler(CallbackQueryHandler(launch_web_ui, pattern = 'web'))
    application.add_handler(conv_updateLogBook)
    application.add_handler(conv_airfieldsearchICAO)
    application.add_handler(conv_airfieldsearchNAME)
    application.add_handler(conv_datesearch)
    application.add_handler(CallbackQueryHandler(airfields, pattern = 'airfieldsVis'))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CallbackQueryHandler(cancel, pattern = 'No'))
    application.add_handler(CallbackQueryHandler(totals, pattern = "totals"))
    application.add_handler(CallbackQueryHandler(LogBook, pattern = "logbook"))



    application.run_polling()
if __name__ == '__main__':
    main()
